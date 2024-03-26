ARG PYTHON_VERSION
FROM mcr.microsoft.com/devcontainers/python:${PYTHON_VERSION}
ENV PYTHONBUFFERED 1
ARG NODE_VERSION="none"
RUN if [ "${NODE_VERSION}" != "none"]; then su vscode -c "umask 0002 && . /usr/local/share/nvm/nvm.sh && nvm install ${NODE_VERSION} 2>&1"; fi
RUN /usr/local/py-utils/bin/pipx install --system-site-packages --pip-args '--no-cache-dir --force-reinstall' poetry && \
    pip install --upgrade pip
RUN chown -R vscode:vscode /home/vscode/.config &&\
    /usr/local/py-utils/bin/poetry completions bash > /etc/bash_completion.d/poetry.bash-completion
