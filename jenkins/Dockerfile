# Jenkins controller with every tool the pipeline needs: Python, Node, Docker CLI,
# kubectl, Ansible and Helm. See docs/runbook.md, "Jenkins".
FROM jenkins/jenkins:2.479.2-lts-jdk17

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 python3-venv python3-pip ansible curl ca-certificates gnupg jq \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && echo "deb [signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian bookworm stable" \
        > /etc/apt/sources.list.d/docker.list \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends docker-ce-cli docker-buildx-plugin nodejs \
    && curl -fsSLo /usr/local/bin/kubectl https://dl.k8s.io/release/v1.31.3/bin/linux/amd64/kubectl \
    && chmod 0755 /usr/local/bin/kubectl \
    && curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash \
    && rm -rf /var/lib/apt/lists/*

USER jenkins
COPY plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt
