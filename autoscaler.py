#!/bin/python
import json
import logging
import os
import time

import requests
from ocdeployer.utils import oc
from prometheus_client.parser import text_string_to_metric_families
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from sh import ErrorReturnCode

log = logging.getLogger(__name__)

NAMESPACE = os.environ.get("NAMESPACE")  # namespace our deployment runs in
if not NAMESPACE:
    try:
        with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r") as f:
            NAMESPACE = f.read()
    except OSError:
        log.error("NAMESPACE not defined, and unable to read namespace file!")
        raise

DC_NAME = os.environ["DC_NAME"]  # name of deployment config we are scaling up/down
METRICS_URL = os.environ["METRICS_URL"]  # kafka prometheus exporter metrics URL
KAFKA_GROUP = os.environ["KAFKA_GROUP"]  # kafka consumer group to monitor
INTERVAL = int(os.environ.get("INTERVAL", 60))  # metric pull interval (seconds)
THRESHOLD = float(os.environ.get("THRESHOLD", 10))  # lag per pod
MIN_PODS = int(os.environ.get("MIN_PODS", 1))  # min pods to scale our deployment to
MAX_PODS = int(os.environ.get("MAX_PODS", 10))  # max pods to scale our deployment to
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

CA_CERT = os.environ.get("CA_CERT", False)
if not CA_CERT:
    log.warn("Disabling SSL Verification. This should not be done in Production.")
    log.warn("To get rid of this message, export CA_CERT=/path/to/ca-certificate")
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def get_num_pods():
    try:
        version = oc(
            "-n",
            NAMESPACE,
            "get",
            "dc",
            DC_NAME,
            "-o",
            "jsonpath={ .status.latestVersion }",
            _exit_on_err=False,
            _reraise=True,
        )
        pods = oc(
            "-n",
            NAMESPACE,
            "get",
            "pods",
            "-l",
            "deployment={}-{}".format(DC_NAME, version),
            "-o",
            "jsonpath={ .items[*].metadata.name }",
            _exit_on_err=False,
            _reraise=True,
        )
    except ErrorReturnCode:
        log.error("Error collecting pod count")
        pods = ""

    num_pods = len(pods.split())
    log.info("Num pods for deployment '%s': %d", DC_NAME, num_pods)
    return num_pods


def get_lag():
    try:
        metrics = requests.get(METRICS_URL).content.decode("utf-8")
    except IOError as err:
        log.error("Failed to query metrics URL: %s", err)
        return None

    total_lag = 0

    for family in text_string_to_metric_families(metrics):
        for sample in family.samples:
            name, labels, value = sample.name, sample.labels, sample.value
            if "lag" in name and labels.get("group") == KAFKA_GROUP:
                log.debug("Adding value from sample: ", sample)
                total_lag += value

    log.info("Total lag for group '%s': %f", KAFKA_GROUP, total_lag)
    return total_lag


def scale_down(pod_count):
    if pod_count <= MIN_PODS:
        log.info("Current pod count is already at or below min pods (%d)", MIN_PODS)
    else:
        oc(
            "scale",
            "--replicas={}".format(pod_count - 1),
            "dc/{}".format(DC_NAME),
            _exit_on_err=False,
        )


def scale_up(pod_count):
    if pod_count >= MAX_PODS:
        log.info("Current pod count is already at or above max pods (%d)", MAX_PODS)
    else:
        oc(
            "scale",
            "--replicas={}".format(pod_count + 1),
            "dc/{}".format(DC_NAME),
            _exit_on_err=False,
        )


if __name__ == "__main__":
    logging.basicConfig(level=getattr(logging, LOG_LEVEL))
    logging.getLogger("sh").setLevel(logging.CRITICAL)
    while True:
        current_num_pods = get_num_pods()
        total_lag = get_lag()
        if current_num_pods is None or total_lag is None:
            log.error("Error collecting pod count or metrics, doing nothing for now...")

        elif total_lag / float(current_num_pods) > THRESHOLD:
            scale_up(current_num_pods)

        elif total_lag / float(current_num_pods) <= THRESHOLD:
            scale_down(current_num_pods)

        else:
            log.error("Couldn't satisfy any if statements, how'd we get here?")

        log.info("Checking again in %d sec", INTERVAL)
        time.sleep(INTERVAL)
