FROM python:3.10-slim

ENV APP_PATH=/usr/src/app
WORKDIR $APP_PATH

RUN apt-get update

RUN apt install -y jq

RUN apt-get update

RUN apt-get install -y --no-install-recommends \
  golang \
  ca-certificates \
  locales \
  fonts-liberation \
  build-essential \
  wget \
  cmake \
  bzip2 \
  curl \
  unzip \
  git \
  gfortran \
  perl \
  patchelf \
  cgroup-tools \
  jq \
  zstd \
  libzstd-dev \
  openssl \
  libssl-dev \
  libsecret-1-0 \
  libcurl4-openssl-dev
RUN echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && locale-gen

RUN ln -fs /usr/share/zoneinfo/Asia/Singapore /etc/localtime

ADD backend .

RUN pip install zef==0.15.6a1

EXPOSE 5010

ENTRYPOINT ["python3", "run_api.py"]
