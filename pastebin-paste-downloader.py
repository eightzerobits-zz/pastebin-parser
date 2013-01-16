#!/usr/bin/python

# This code was derived by code posted by Michiel Overtoom (http://www.michielovertoom.com/python/pastebin-abused/)
# Copyright (c) 2012, Bryan Brannigan, Ben Jackson
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright notice,
#       this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice,this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the copyright holder nor the names of its
#       contributors may be used to endorse or promote products derived from
#       this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"""
This code is intended to retrieve paste IDs from a remote queue.  Each paste is downloaded and sent to a queue for processing.

Dependancies: BeautifulSoup,pika

This code might cause the world to implode.  Run at your own risk.  
"""

import sys, os, time, datetime, random, pika, logging, argparse, urllib2, threading
from ConfigParser import SafeConfigParser
from urllib2 import Request, urlopen, URLError, HTTPError
config = SafeConfigParser()
config.read('config.ini')

parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbose", help="Increase logging verbosity", action="store_true")
args = parser.parse_args()

if args.verbose:
    log_level = logging.DEBUG
else:
    log_level = logging.INFO

logging.basicConfig(filename='pastebin-downloader.log',format='%(asctime)s %(message)s',level=log_level)

def get_url_content(url):

    req_headers = {
        'User-Agent': 'Mozilla/5.0 (compatible;)',
        'Referer': 'http://pastebin.com'
    }

    try:
        url_request = urllib2.Request(url, None, req_headers)
        opener = urllib2.build_opener()
        content = opener.open(url_request).read()
    except HTTPError, e:
        logging.warn("Bombed out on %s... HTTP Error (%s)... Letting it go..." % (url, e.code))
        return e
    except URLError, e:
        logging.warn("Bombed out on %s... URL Error (%s)... Letting it go..." % (url, e.reason))
        return e

    return content

def downloader(ch, method, properties, paste):

    content = get_url_content("http://pastebin.com/raw.php?i=" + paste)

    if isinstance(content, EnvironmentError):
        ch.basic_ack(delivery_tag = method.delivery_tag)
        logging.warn("Possible Bannination... Sleeping 30 minutes...")
        time.sleep(1800)
    else:
        if content == 'Hey, it seems you are requesting a little bit too much from Pastebin. Please slow down!':
            logging.warn("Throttling... requeuing %s..." % (paste))
            ch.basic_publish(exchange='',routing_key='pastes',body=paste, properties=pika.BasicProperties(delivery_mode = 2,))
            time.sleep(2)
        else:
            logging.info("Downloaded %s..." % (paste))
            ch.basic_publish(exchange='',routing_key='pastes_data',body=content, properties=pika.BasicProperties(delivery_mode = 2,correlation_id=paste)) 
            logging.debug("%s Queued for Parsing..." % (paste))
	    ch.basic_ack(delivery_tag = method.delivery_tag)
    sleepytime = random.uniform(5, 10)
    logging.debug("I am sleeping %s seconds..." % (str(sleepytime)))
    time.sleep(sleepytime)

def downloader_thread():

    mq = pika.BlockingConnection(pika.ConnectionParameters(config.get('rabbitmq', 'hostname'), int(config.get('rabbitmq', 'port')), '/', pika.credentials.PlainCredentials(config.get('rabbitmq', 'username'),config.get('rabbitmq', 'password'))))

    channel = mq.channel()
    channel.queue_declare(queue='pastes', durable=True)
    channel.queue_declare(queue='pastes_data', durable=True)

    try:
        logging.info("Spinning Up Downloader...")
        channel.basic_qos(prefetch_count=1)
	channel.basic_consume(downloader,queue='pastes',no_ack=False)
	channel.start_consuming()
    except pika.exceptions.ConnectionClosed:
        logging.warn("Connection unexpectedly closed! Abandon ship!")
    except KeyboardInterrupt:
        logging.info("Warning! Keyboard Interrupted Detected. Attempting to hard land...")
        channel.stop_consuming()
    finally:
        mq.close()
        return

while True:
    thread = threading.Thread(target=downloader_thread)
    thread.start()
    thread.join()
    logging.warn("Uh Oh! Looks like the thread bombed out. Trying to fix...")

