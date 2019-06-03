FROM registry.access.redhat.com/rhscl/python-36-rhel7

USER 0

ENV OC_VERSION=v3.11.0 \
    OC_TAG_SHA=0cbc58b

RUN curl -sLo /tmp/oc.tar.gz https://github.com/openshift/origin/releases/download/${OC_VERSION}/openshift-origin-client-tools-${OC_VERSION}-${OC_TAG_SHA}-linux-64bit.tar.gz && \
    tar xzvf /tmp/oc.tar.gz -C /tmp/ && \
    mv /tmp/openshift-origin-client-tools-${OC_VERSION}-${OC_TAG_SHA}-linux-64bit/oc /usr/local/bin/ && \
    rm -rf /tmp/oc.tar.gz /tmp/openshift-origin-client-tools-${OC_VERSION}-${OC_TAG_SHA}-linux-64bit

USER 1001

WORKDIR /opt/app-root/src
COPY . .

RUN scl enable rh-python36 "pip install --upgrade pip && \
                            pip install pipenv && \
                            pipenv install --system"

CMD ["python", "autoscaler.py"]
