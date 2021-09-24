FROM python:3.9
ARG YANG_ID
ARG YANG_GID

ENV YANG_ID "$YANG_ID"
ENV YANG_GID "$YANG_GID"
ENV VIRTUAL_ENV=/documentation

RUN apt-get -y update
RUN apt-get -y install nodejs ruby-full

RUN groupadd -g ${YANG_GID} -r yang \
    && useradd --no-log-init -r -g yang -u ${YANG_ID} -d $VIRTUAL_ENV yang

RUN gem install bundler

WORKDIR $VIRTUAL_ENV
RUN git clone https://github.com/slatedocs/slate.git
COPY . $VIRTUAL_ENV

WORKDIR $VIRTUAL_ENV/slate
RUN rm -rf source
RUN cp -R ../source .
RUN bundle install
RUN bundle exec middleman build --clean

RUN mkdir -p /usr/share/nginx/html
RUN cp -R $VIRTUAL_ENV/slate /usr/share/nginx/html

CMD chown -R yang:yang /usr/share/nginx/html/slate
