FROM paulgauthier/aider

USER root
SHELL ["/bin/bash", "-c"]
RUN apt-get update && \
    apt-get install -y ripgrep && \
    . /venv/bin/activate && \
    pip install ra-aid==0.13.2
