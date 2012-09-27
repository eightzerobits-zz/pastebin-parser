#!/usr/bin/python

# This code was derived by code posted by Michiel Overtoom (http://www.michielovertoom.com/python/pastebin-abused/)
# Copyright (c) 2012, Bryan Brannigan
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
This code is intended to retrieve a list of pastes from pastebin once per minute.  Each paste is then individual downloaded and searched for strings which are defined in the searchstrings.txt file.  

Dependancies: BeautifulSoup,pymongo

This code might cause the world to implode.  Run at your own risk.  
"""

import sys, os, time, datetime, random, smtplib
import BeautifulSoup, threading, Queue, pymongo

from email import encoders
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib2 import Request, urlopen, URLError, HTTPError
from pymongo import Connection
from ConfigParser import SafeConfigParser

connection = Connection()
db = connection.datastore
collection = db.pastes

config = SafeConfigParser()
config.read('config.ini')

pastesseen = set()
pastes = Queue.Queue()

log = open("log.txt", "wt")

searchstringsfile = open("searchstrings.txt")
searchstrings = searchstringsfile.readlines()

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

def safe_unicode(obj, *args):
    """ return the unicode representation of obj """
    try:
        return unicode(obj, *args)
    except UnicodeDecodeError:
        # obj is byte string
        ascii_text = str(obj).encode('string_escape')
        return unicode(ascii_text)

def downloader():
    while True:
        paste = pastes.get()

        content = get_url_content("http://pastebin.com/raw.php?i=" + paste)

        if not (content):
            pastes.task_done()
            continue

	if "requesting a little bit too much" in content:
  	   log.write("Throttling... requeuing %s... (%d left)\n" % (paste, pastes.qsize()))
	   pastes.put(paste)
	   time.sleep(0.1)
	else:
	   log.write("Downloaded %s... (%d left)\n" % (paste, pastes.qsize())) 
	   pastedb = {"pastesource": "Pastebin", "pasteid": paste, "insertdate": datetime.datetime.utcnow(), "content": safe_unicode(content)}
	   insid = collection.insert(pastedb)
	   log.write("%s Inserted... (%s)\n" % (paste, insid)) 

	   for s in searchstrings:
		if s.strip().lower() in content.lower():
		    log.write(s.strip() + " found in %s\n" % paste) 
		    emailalert(content,s.strip(),paste)

        log.flush()
	time.sleep(random.uniform(1, 3))
        pastes.task_done()

def scraper():
    failures = 0
    while True:

        content = get_url_content("http://www.pastebin.com/archives/")

        if not (content):
            time.sleep(10)
            failures += 1

            #Three failures in a row? Go into a holding pattern.
            if failures > 2:
                time.sleep(300)

            continue

        failures = 0

        soup = BeautifulSoup.BeautifulSoup(content)
        for link in soup.findAll('a'):
           href = link.get('href')
           if '/' in href[0] and len(href) == 9 and href != "settings" and href != "archvies":
              href = href[1:] # chop off leading /
              dupe_check = {"pastesource": "Pastebin", "pasteid": href}
              if collection.find_one(dupe_check) is None:
                  pastes.put(href)
                  pastesseen.add(href)
                  log.write("%s queued for download\n" % href)
              else:
                  log.write("%s is a dupe. Not queued.\n" % href)

	log.flush() 
        time.sleep(60)

def emailalert(content,keyword,paste):
    outer = MIMEMultipart()
    outer['Subject'] = 'Pastebin Parser Alert - Keyword: %s - Paste: %s' % (paste,keyword)
    outer['To'] = ', '.join(config.get('mail','receivers'))
    outer['From'] = config.get('mail', 'sender')

    msg = MIMEText(content, 'plain')
    msg.add_header('Content-Disposition', 'attachment', filename='content.txt')
    outer.attach(msg)
    composed = outer.as_string()
    s = smtplib.SMTP(config.get('mail', 'smtpserver'))
    s.sendmail(config.get('mail', 'sender'),config.get('mail', 'receivers').split(','),composed)
    s.quit()

num_workers = 6
for i in range(num_workers):
    t = threading.Thread(target=downloader)
    t.setDaemon(True)
    t.start()

s = threading.Thread(target=scraper)
s.start()
s.join()
