#!/bin/python
import json
import os
import time

import requests
from ocdeployer.utils import oc
from prometheus_client.parser import text_string_to_metric_families
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from sh import ErrorReturnCode


TOKEN = os.environ['TOKEN']
NAMESPACE = os.environ['NAMESPACE']
DC_NAME = os.environ['DC_NAME']
METRICS_URL = os.environ['METRICS_URL']
KAFKA_GROUP = os.environ['KAFKA_GROUP']
INTERVAL = os.environ.get('METRIC_PULL_INTERVAL_SECONDS', 60)
THRESHOLD = os.environ.get('THRESHOLD', 0.7)
MIN_PODS = os.environ.get('MIN_PODS', 1)
MAX_PODS = os.environ.get('MAX_PODS', 10)
CA_CERT = os.environ.get('CA_CERT', False)


if not CA_CERT:
    log.warn("Disabling SSL Verification. This should not be done in Production.")
    log.warn("To get rid of this message, export CA_CERT=/path/to/ca-certificate")
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def get_num_pods():
    try:
        version = oc("-n", NAMESPACE, "get", "dc", DC_NAME, "-o", "jsonpath={ .status.latestVersion }")
        pods = oc("-n", NAMESPACE, "get", "pods", "-l", "deployment={}-{}".format(DC_NAME, version)), "-o", "jsonpath={ .items[*].metadata.name }")
    except ErrorReturnCode:
        log.exception("Error collecting pod count")

    num_pods = len(pods.split())
    log.info("Num pods for deployment '%s': %d", DC_NAME, num_pods)
    return num_pods


def get_lag():
    try:
        metrics = requests.get(METRICS_URL).content
    except IOError:
        log.exception("Failed to query metrics URL")
        return None

    total_lag = 0
    
    for family in text_string_to_metric_families(metrics):
        for sample in family.samples:
            name, labels, value = sample.name, sample.labels, sample.value
            if "lag" in name and labels.get('group') == KAFKA_GROUP:
                log.debug("Adding value from sample: ", sample)
                total_lag += value

    log.info("Total lag for group '%s': %d", total_lag, KAFKA_GROUP)


def scale_down(pod_count):
    if pod_count <= MIN_PODS:
        log.info("Pod count (%d) is already at or below min pods (%d)", num_pods, MIN_PODS)
    else:
        oc("scale", "--replicas={}".format(pod_count - 1), "dc/{}".format(DC_NAME))


def scale_up(pod_count):
    if pod_count >= MAX_PODS:
        log.info("Pod count (%d) is already at or above max pods (%d)", num_pods, MAX_PODS)
    else:
        oc("scale", "--replicas={}".format(pod_count + 1), "dc/{}".format(DC_NAME))


while True:
    current_num_pods = get_num_pods()
    total_lag = get_lag()
    if num_pods is None or total_lag is None:
        log.error("Error collecting pod count or metrics, doing nothing for now...")

    elif total_lag / float(num_pods) > THRESHOLD:
        scale_up(current_num_pods)

    elif total_lag / float(num_pods) <= THRESHOLD:
        scale_down(current_num_pods)

    else:
        log.error("Couldn't satisfy any if statements, how'd we get here?")

    time.sleep(INTERVAL)
