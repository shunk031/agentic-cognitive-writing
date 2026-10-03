FROM texlive/texlive:latest-small

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV NO_PROXY=${NO_PROXY}

RUN tlmgr install inconsolata dblfloatfix sttools epigraph nextpage helvetic
