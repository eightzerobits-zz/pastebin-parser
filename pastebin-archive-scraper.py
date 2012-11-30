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
This code is intended to retrieve a list of pastes from pastebin once per minute.  Each paste is then queued to be individually downloaded and processed by the paste downloader.  

Dependancies: BeautifulSoup,pymongo,pika,RabbitMQ

This code might cause the world to implode.  Run at your own risk.  
"""

import sys, os, time, datetime, BeautifulSoup, threading, pika, sqlite3

from urllib2 import Request, urlopen, URLError, HTTPError
from ConfigParser import SafeConfigParser

log = open("log.txt", "a")
config = SafeConfigParser()
config.read('config.ini')

mq = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = mq.channel()
channel.queue_declare(queue='pastes', durable=True)

dupesdb = sqlite3.connect('dupes.db')
cur = dupesdb.cursor()
cur.execute("DROP TABLE IF EXISTS dupes")
cur.execute("CREATE TABLE dupes(href TEXT)")

def scraper():
    failures = 0
    while True:
        content = get_url_content("http://www.pastebin.com/archives/")
        if not (content):
            time.sleep(10)
            failures += 1
            #Three failures in a row? Go into a holding pattern.
            if failures > 2:
                log.write("3 Failures in a row. Holding Pattern")
                time.sleep(450)
                failures = 0
            continue
        failures = 0
        links = 0
        inserts = 0
        dupes = 0
        soup = BeautifulSoup.BeautifulSoup(content)
        for link in soup.html.table.findAll('a'):
           href = link.get('href')
           if '/' in href[0] and len(href) == 9:
              links += 1
              href = href[1:] # chop off leading /
              cur.execute("SELECT href FROM dupes WHERE href = '%s'" % (href)) 
	      dupe_check = cur.fetchall()
	      
	      if not dupe_check:
                  channel.basic_publish(exchange='',
					routing_key='pastes',
					body=href,
					properties=pika.BasicProperties(
						delivery_mode = 2,
					))
		  cur.execute("INSERT INTO dupes VALUES('%s')" % (href)) 
		  inserts += 1
              else:
                  dupes += 1

        log.write("%d links found. %d queued, %d duplicates\n" % (links, inserts, dupes))
	log.flush()
        time.sleep(60)

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

#s = threading.Thread(target=scraper)
#s.setDaemon(True)
#s.start()

log.write("Pastebin Archive Scraper is Go\n")
while True:
	scraper()
mq.close()
