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

Dependancies: BeautifulSoup

This code might cause the world to implode.  Run at your own risk.  
"""

import BeautifulSoup
import urllib2
import time
import Queue
import threading
import sys
import datetime
import random
import os
import smtplib
from email import encoders
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

sender = 'pastebin-parser@example.net'
receivers = ['you@example.net']
smtpserver = '127.0.0.1'

pastesseen = set()
pastes = Queue.Queue()

searchstringsfile = open("searchstrings.txt")
searchstrings = searchstringsfile.readlines()

def downloader():
    while True:
        paste = pastes.get()
        delay = 1.1 # random.uniform(1, 3)
        fn = "pastebins/%s-%s.txt" % (paste, datetime.datetime.today().strftime("%Y-%m-%d"))
        content = urllib2.urlopen("http://pastebin.com/raw.php?i=" + paste).read()
	if "requesting a little bit too much" in content:
  	   print "Throttling... requeuing %s" % paste
	   pastes.put(paste)
	   time.sleep(0.1)
	else:
	   for s in searchstrings:
		if s.strip().lower() in content.lower():
			print s.strip() + " found" 
		  	f = open(fn, "wt")
	          	f.write(content)
	          	f.close()
        	  	sys.stdout.write("Downloaded %s, waiting %f sec\n" % (paste, delay))
		  	emailalert(content,s.strip(),paste)
        delay = 1.1 # random.uniform(1, 3)
        time.sleep(delay)
        pastes.task_done()

def scraper():
    scrapecount = 1
    while scrapecount:
        html = urllib2.urlopen("http://www.pastebin.com/archives/").read()
        soup = BeautifulSoup.BeautifulSoup(html)
        for link in soup.findAll('a'):
            href = link.get('href')
            if '/' in href[0] and len(href) == 9:
	        if href in pastesseen:
                    sys.stdout.write("%s already seen\n" % href)
                else:
                    href = href[1:] # chop off leading /
                    pastes.put(href)
                    pastesseen.add(href)
                    sys.stdout.write("%s queued for download\n" % href)
        delay = 12 # random.uniform(6,10)
        time.sleep(delay)
        scrapecount = 1

def emailalert(content,keyword,paste):
    outer = MIMEMultipart()
    outer['Subject'] = 'Pastebin Parser Alert %s' % keyword
    outer['To'] = ', '.join(receivers)
    outer['From'] = sender
    msg = MIMEText(content, 'plain')
    msg.preamble = 'From paste %s' % paste
    msg.add_header('Content-Disposition', 'attachment', filename='content.txt')
    outer.attach(msg)
    composed = outer.as_string()
    s = smtplib.SMTP(smtpserver)
    s.sendmail(sender,receivers,composed)
    s.quit()

num_workers = 2
for i in range(num_workers):
    t = threading.Thread(target=downloader)
    t.setDaemon(True)
    t.start()

if not os.path.exists("pastebins"):
    os.mkdir("pastebins") # Thanks, threecheese!

s = threading.Thread(target=scraper)
s.start()
s.join()
