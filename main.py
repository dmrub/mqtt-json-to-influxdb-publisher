#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
    MQTT JSON to InfluxDB Publisher
    ~~~~~~~~~~

    :copyright: (c) 2017-2019 German Research Center for Artificial Intelligence (DFKI)
    :author: Dmitri Rubinstein
    :license: Apache License 2.0, see LICENSE file for more details
"""

from __future__ import print_function
import logging
from logging.handlers import RotatingFileHandler

# Init default console handler

# LOG_FORMAT = '%(asctime)s %(message)s'
LOG_FORMAT = '%(asctime)s %(levelname)s %(pathname)s:%(lineno)s: %(message)s'
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
root_logger = logging.getLogger()
root_logger.setLevel(logging.WARNING)
root_logger.addHandler(console_handler)

logger = logging.getLogger('main')
logger.setLevel(logging.WARNING)

import sys
import six
import os.path
import signal
import argparse
import paho.mqtt.client as mqtt
import time
import concurrent.futures
import requests
import urllib.parse
from threading import Timer, Lock
from collections import namedtuple
import json


def set_loggers_level(loggers, level):
    for i in loggers:
        if isinstance(i, logging.Logger):
            lgr = i
        else:
            lgr = logging.getLogger(i)
        lgr.setLevel(level)


def slash_at_end(s):
    if s.endswith("/"):
        return s
    else:
        return s + "/"


# Note: paho mqtt require type 'str' for topics


def make_status_topic(topic_root):
    return str(slash_at_end(topic_root) + "status")


class Publisher(object):

    def __init__(self, args):
        self.args = args
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.executor = None
        self.exit_flag = False
        if args.influxdb_uri and args.influxdb_dbname:
            self.influxdb_write_uri = "{}/write?db={}".format(args.influxdb_uri, args.influxdb_dbname)
        else:
            self.influxdb_write_uri = None

        self._lock = Lock()
        self._last_states = {}
        self._last_update_unix_ts = None

        self._dist_lock = Lock()
        self._last_dist_ts = None
        self._num_dist_msg = 0

    def run(self):
        logger.info('Connecting to MQTT host {} port {}'.format(self.args.mqtt_host, self.args.mqtt_port))
        self.client.connect(self.args.mqtt_host, self.args.mqtt_port, 60)

        self.executor = concurrent.futures.ThreadPoolExecutor()

        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("once")

            # Blocking call that processes network traffic, dispatches callbacks and
            # handles reconnecting.
            # Other loop*() functions are available that give a threaded interface and a
            # manual interface.
            self.client.loop_forever()

    def close(self):
        self.exit_flag = True
        self.client.disconnect()
        self.executor.shutdown()

    def on_connect(self, client, userdata, flags, rc):
        """The callback for when the client receives a CONNACK response from the server."""
        logger.info("Connected with result code " + str(rc))

        subscr_topics = [(t, self.args.mqtt_qos) for t in self.args.mqtt_topics]

        try:
            # Subscribing in on_connect() means that if we lose the connection and
            # reconnect then subscriptions will be renewed.
            result, mid = self.client.subscribe(subscr_topics)
            if result == mqtt.MQTT_ERR_SUCCESS:
                logger.info('Successfully subscribed to topics: %r', subscr_topics)
            else:
                logger.error('Could not subscribe to topics %r, MQTT error code: %s', subscr_topics, result)
        except Exception as e:
            logger.exception("Unexpected error: %r", e)

    def on_message(self, client, userdata, msg):
        """The callback for when a PUBLISH message is received from the server."""
        logger.info("Received MQTT message: topic={} payload={!r}".format(msg.topic, msg.payload))

        # Process messages
        if msg:
            self.on_json_message(client, userdata, msg)

    def on_json_message(self, client, userdata, msg):
        unix_ts = time.time()

        try:
            json_payload = json.loads(msg.payload)
        except ValueError:
            logger.exception("Message payload with topic %s is not in JSON format: %r", msg.topic, msg.payload)
            return

        if not isinstance(json_payload, dict):
            logger.error("Message payload with topic %s is not a dictionary: %r", msg.topic, msg.payload)
            return

        self.update_influxdb(msg.topic, json_payload, unix_ts)

    def update_influxdb(self, measurement, data, unix_ts):
        self.executor.submit(self.update_influxdb_sync, measurement=measurement, data=data, unix_ts=unix_ts)

    def update_influxdb_sync(self, measurement, data, unix_ts):
        if not self.influxdb_write_uri:
            return

        ts = int(unix_ts * 1000000000)
        with requests.Session() as s:
            for k, v in six.iteritems(data):

                if isinstance(v, six.integer_types + (float,)):
                    value = v
                elif isinstance(v, six.string_types):
                    try:
                        value = str(int(v))
                    except ValueError:
                        try:
                            value = str(float(v))
                        except ValueError:
                            # FIXME This is not a full quotation solution for InfluxDB
                            value = '"{}"'.format(v.replace('"', '\\"'))
                else:
                    continue

                influxdb_entry = "{} {}={} {}".format(measurement, k, value, ts)
                logger.info("InfluxDB Entry: {}".format(influxdb_entry))
                try:
                    headers = {
                        # 'content-type': "application/json",
                    }
                    res = s.post(self.influxdb_write_uri, data=influxdb_entry, headers=headers,
                                 verify=False)
                    res.raise_for_status()
                    logger.info('InfluxDB entry successfully created')
                except requests.RequestException as e:
                    logger.exception("Request failed: payload: %r, error: %r", influxdb_entry, e)
                except Exception as e:
                    logger.exception("Unexpected error: payload: %r, error: %r", influxdb_entry, e)


if __name__ == "__main__":

    default_log_file = "mqtt-json-to-influxdb-publisher.log"

    parser = argparse.ArgumentParser(
        description="Run MQTT to JSON InfluxDB Publisher.",
        usage="\n%(prog)s [options]",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-d", "--debug", action="store_true",
                        help="enable debug mode")
    parser.add_argument("-c", "--log-to-console", action="store_true",
                        help="output log to console", default=False)
    parser.add_argument("-l", "--log-file", nargs='?',
                        help="output log to file", metavar="FILE", type=str,
                        const=default_log_file,
                        default=None)
    parser.add_argument("--log-max-bytes",
                        help="Rollover whenever the current log file is nearly MAX_BYTES in length",
                        metavar="MAX_BYTES", type=int,
                        default=1024 * 1024 * 1)
    parser.add_argument("--log-backup-count",
                        help="If BACKUP_COUNT is non-zero, the system will save old log files by appending the "
                             "extensions '.1', '.2' etc., to the filename.",
                        metavar="BACKUP_COUNT", type=int,
                        default=3)
    parser.add_argument("--mqtt-host", action="store", default="localhost",
                        help="MQTT server host")
    parser.add_argument("--mqtt-port", action="store", default=1883, type=int,
                        help="MQTT server port", )
    parser.add_argument("--influxdb-uri", action="store",
                        default="http://localhost:8086",
                        help="InfluxDB API URI")
    parser.add_argument("--influxdb-dbname", action="store", default="mqtt",
                        help="InfluxDB database name")
    parser.add_argument("--mqtt-topics", action="store", default=["#"],
                        metavar='MQTT_TOPIC', nargs='+',
                        help="MQTT topics to subscribe")
    parser.add_argument('--mqtt-qos', action="store",
                        help="MQTT QoS value for messages", metavar='QOS', type=int,
                        choices=[0, 1, 2],
                        default=0)

    parser.add_argument("--version", action="version",
                        version="%(prog)s 0.1")
    # parser.add_argument("args", nargs="*", help=argparse.SUPPRESS)

    args = parser.parse_args(sys.argv[1:])

    debug = args.debug

    handler = None

    # Configure application

    log_handler = console_handler

    if not args.log_to_console and not args.log_file:
        args.log_file = default_log_file

    if not args.log_to_console:
        print("Logging to console is disabled", file=sys.stderr)
        root_logger.removeHandler(console_handler)
    else:
        print("Logging to console is enabled", file=sys.stderr)

    if args.log_file:
        log_file = os.path.abspath(args.log_file)
        print("Logging to file {}".format(log_file), file=sys.stderr)
        logdir = os.path.dirname(log_file)
        if logdir and not os.path.exists(logdir):
            os.makedirs(logdir)
        log_handler = RotatingFileHandler(log_file, maxBytes=args.log_max_bytes, backupCount=args.log_backup_count)
        if args.debug:
            log_handler.setLevel(logging.DEBUG)
        log_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root_logger.addHandler(log_handler)

    if args.debug:
        set_loggers_level((logger,), logging.DEBUG)

    logger.info('Environment:')
    for k, v in os.environ.items():
        logger.info('%s = %r' % (k, v))

    # Initialize application
    logger.info('Starting application')
    logger.info('MQTT topics: {}'.format(args.mqtt_topics))

    publisher = Publisher(args)


    def signal_term_handler(signal, frame):
        print('Got signal {}, exiting'.format(signal), file=sys.stderr)
        logger.info('Got signal {}, exiting'.format(signal))
        publisher.close()
        sys.exit(0)


    signal.signal(signal.SIGTERM, signal_term_handler)
    signal.signal(signal.SIGINT, signal_term_handler)

    publisher.run()
