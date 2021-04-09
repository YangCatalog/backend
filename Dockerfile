FROM python:3.9
ARG YANG_ID
ARG YANG_GID

ENV YANG_ID "$YANG_ID"
ENV YANG_GID "$YANG_GID"
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONUNBUFFERED=1

ENV VIRTUAL_ENV=/backend

#Install Cron
RUN apt-get -y update
RUN apt-get -y install nodejs libv8-dev ruby-full cron gunicorn logrotate curl

RUN echo postfix postfix/mailname string yang2.amsl.com | debconf-set-selections; \
    echo postfix postfix/main_mailer_type string 'Internet Site' | debconf-set-selections; \
    apt-get -y install postfix rsyslog systemd
RUN apt-get -y autoremove

RUN gem install bundler

RUN groupadd -g ${YANG_GID} -r yang \
  && useradd --no-log-init -r -g yang -u ${YANG_ID} -d $VIRTUAL_ENV yang \
  && pip install virtualenv \
  && virtualenv --system-site-packages $VIRTUAL_ENV \
  && mkdir -p /etc/yangcatalog

COPY . $VIRTUAL_ENV
ENV PYTHONPATH=$VIRTUAL_ENV/bin/python
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV GIT_PYTHON_GIT_EXECUTABLE=/usr/bin/git

WORKDIR $VIRTUAL_ENV

RUN pip install -r requirements.txt \
  && ./setup.py install

ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Add crontab file in the cron directory
COPY crontab /etc/cron.d/yang-cron

RUN mkdir /var/run/yang

RUN chown yang:yang /etc/cron.d/yang-cron
RUN chown -R yang:yang $VIRTUAL_ENV
RUN chown -R yang:yang /var/run/yang

RUN mkdir /var/run/mysqld
RUN chown -R yang:yang /var/run/mysqld
RUN chmod 777 /var/run/mysqld

COPY yangcatalog-rotate /etc/logrotate.d/yangcatalog-rotate

RUN chmod 644 /etc/logrotate.d/yangcatalog-rotate

USER ${YANG_ID}:${YANG_GID}

RUN git clone https://github.com/slatedocs/slate.git

WORKDIR $VIRTUAL_ENV/slate

RUN rm -rf source
RUN cp -R ../documentation/source .

WORKDIR $VIRTUAL_ENV

# Apply cron job
RUN crontab /etc/cron.d/yang-cron

USER root:root
WORKDIR $VIRTUAL_ENV/slate
RUN bundle install
RUN bundle exec middleman build --clean
WORKDIR $VIRTUAL_ENV
RUN mkdir -p /usr/share/nginx/html/stats
RUN cp -R $VIRTUAL_ENV/slate /usr/share/nginx/html
RUN chown -R yang:yang /usr/share/nginx
RUN ln -s /usr/share/nginx/html/stats/statistics.html /usr/share/nginx/html/statistics.html

CMD chown -R yang:yang /var/run/yang && cron && service postfix start && service rsyslog start && /backend/bin/gunicorn api.wsgi:application -c gunicorn.conf.py

EXPOSE 3031
