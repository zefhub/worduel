# Copyright (c) 2022 Synchronous Technologies Pte Ltd
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

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
