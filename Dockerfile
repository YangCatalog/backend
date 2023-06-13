FROM python:3.10-bullseye
ARG YANG_ID
ARG YANG_GID
ARG CRON_MAIL_TO
ARG YANGCATALOG_CONFIG_PATH

ENV YANG_ID "$YANG_ID"
ENV YANG_GID "$YANG_GID"
ENV CRON_MAIL_TO "$CRON_MAIL_TO"
ENV YANGCATALOG_CONFIG_PATH "$YANGCATALOG_CONFIG_PATH"
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONUNBUFFERED=1

ENV VIRTUAL_ENV=/backend
ENV BACKEND=/backend
ENV PYANG_PLUGINPATH="$BACKEND/opensearch_indexing/pyang_plugin"

#Install Cron
RUN apt-get -y update && apt-get -y install libv8-dev cron gunicorn logrotate curl mydumper rsync vim pcregrep

RUN echo postfix postfix/mailname string yangcatalog.org | debconf-set-selections; \
    echo postfix postfix/main_mailer_type string 'Internet Site' | debconf-set-selections; \
    apt-get -y install postfix rsyslog systemd
RUN apt-get -y autoremove

COPY ./resources/main.cf /etc/postfix/main.cf

RUN groupadd -g ${YANG_GID} -r yang \
  && useradd --no-log-init -r -g yang -u ${YANG_ID} -d $VIRTUAL_ENV yang \
  && pip install virtualenv \
  && virtualenv --system-site-packages $VIRTUAL_ENV \
  && mkdir -p /etc/yangcatalog

ENV PYTHONPATH="$VIRTUAL_ENV:$VIRTUAL_ENV/bin/python"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV GIT_PYTHON_GIT_EXECUTABLE=/usr/bin/git

WORKDIR $VIRTUAL_ENV

RUN mkdir /var/run/yang
RUN chown -R yang:yang /var/run/yang

RUN mkdir -p /usr/share/nginx/html/stats
RUN chown -R yang:yang /usr/share/nginx
RUN ln -s /usr/share/nginx/html/stats/statistics.html /usr/share/nginx/html/statistics.html

COPY ./backend/requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=yang:yang ./backend $VIRTUAL_ENV

# Add crontab file in the cron directory
COPY --chown=yang:yang ./backend/crontab /etc/cron.d/yang-cron

RUN sed -i "s|<MAIL_TO>|${CRON_MAIL_TO}|g" /etc/cron.d/yang-cron
RUN sed -i "s|<YANGCATALOG_CONFIG_PATH>|${YANGCATALOG_CONFIG_PATH}|g" /etc/cron.d/yang-cron
RUN sed -i "/imklog/s/^/#/" /etc/rsyslog.conf

COPY ./backend/yangcatalog-rotate /etc/logrotate.d/yangcatalog-rotate

RUN chmod 644 /etc/logrotate.d/yangcatalog-rotate

USER ${YANG_ID}:${YANG_GID}

WORKDIR $VIRTUAL_ENV

# Apply cron job
RUN crontab /etc/cron.d/yang-cron

USER root:root
CMD cron && service postfix start && service rsyslog start && /backend/bin/gunicorn api.wsgi:application -c gunicorn.conf.py

EXPOSE 3031
