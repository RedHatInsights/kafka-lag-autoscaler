# kafka-lag-autoscaler
Scale an openshift deployment up/down based on Prometheus kafka lag metrics

This is a POC demonstrating how a pod running in OpenShift can be used to periodically query a kafka prometheus exporter URL and use the lag metrics for a consumer group to scale a deployment up/down.

It runs using the following env vars:
`NAMESPACE` - namespace the deployment that you want to scale up/down runs in (if none provided, tries to look up the namespace it's currently running in)
`DC_NAME` - name of deployment config we are scaling up/down
`METRICS_URL` - kafka prometheus exporter metrics URL
`KAFKA_GROUP` - name of kafka consumer group to monitor
`INTERVAL` - metric pull interval (seconds) -- this is how often we check if a scale is needed (default: 60)
`THRESHOLD` - lag per pod threshold. If above this, we scale up. If below this, we scale down (default: 10)
`MIN_PODS` - min pods to scale our deployment to (default: 1)
`MAX_PODS` - max pods to scale our deployment to (default: 10)
`LOG_LEVEL` - logging level (default: INFO)
`CA_CERT` - path to CA certificate used for HTTPS queries to the METRICS_URL. If none specified, SSL validation is turned off

Example to deploy into your project for testing:
```
$ oc project myproject
$ oc process -p METRICS_URL="http://kafka-lag-exporter.someproject.svc:9208/metrics" -p NAMESPACE=myproject -p DC_NAME="mydc" -p KAFKA_GROUP="my_consumer" -f template.yaml | oc apply -f -
```

By default the pod will run using the `default` service account. You will need to give this service account enough permissions in your namespace to get pods and scale deployments up/down (the `edit` role in OpenShift will do the job). You can also specify a different service account for this app to use by setting the `SERVICE_ACCOUNT_NAME` parameter on the template.
