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

import sys, os, time, datetime, random, pika
from ConfigParser import SafeConfigParser
from urllib2 import Request, urlopen, URLError, HTTPError
config = SafeConfigParser()
config.read('config.ini')

log = open("downloader-log.txt", "a")

mq = pika.BlockingConnection(pika.ConnectionParameters(config.get('rabbitmq', 'hostname'), int(config.get('rabbitmq', 'port')), '/', pika.credentials.PlainCredentials(config.get('rabbitmq', 'username'),config.get('rabbitmq', 'password'))))

channel = mq.channel()
channel.queue_declare(queue='pastes', durable=True)
channel.queue_declare(queue='pastes_data', durable=True)

def get_url_content(url):

    req_headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:14.0) Gecko/20100101 Firefox/14.0.1',
        'Referer': 'http://pastebin.com'
    }

    try:
        content = urlopen(url).read()
    except HTTPError, e:
        log.write("Bombed out on %s... HTTP Error (%s)... Letting it go...\n" % (url, e.code))
        return 0
    except URLError, e:
        log.write("Bombed out on %s... URL Error (%s)... Letting it go...\n" % (url, e.reason))
        return 0

    return content

def downloader(ch, method, properties, paste):

        content = get_url_content("http://pastebin.com/raw.php?i=" + paste)

        if not (content):
	    ch.basic_ack(delivery_tag = method.delivery_tag)

        else:
		if content == 'Hey, it seems you are requesting a little bit too much from Pastebin. Please slow down!':
		    log.write("Throttling... requeuing %s...\n" % (paste))
		    ch.basic_publish(exchange='',routing_key='pastes',body=paste, properties=pika.BasicProperties(delivery_mode = 2,))
      		    time.sleep(2)
        	else:
            		log.write("Downloaded %s...\n" % (paste))
            		ch.basic_publish(exchange='',routing_key='pastes_data',body=content, properties=pika.BasicProperties(delivery_mode = 2,correlation_id=paste)) 
	    		log.write("%s Queued for Parsing...\n" % (paste))
			ch.basic_ack(delivery_tag = method.delivery_tag)

        log.flush()
        time.sleep(random.uniform(3, 5))

while True:

        log.write("Spinning Up Downloader Thread...\n")
	channel.basic_consume(downloader,queue='pastes',no_ack=False)
	channel.start_consuming()
