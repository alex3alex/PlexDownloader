#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Ilyaz <>
# URL: https://github.com/ilyaz/PlexDownloader
#
# This file is part of PlexDownloader.
#
# PlexDownlaoder is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PlexDownloader is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PlexDownloader.  If not, see <http://www.gnu.org/licenses/>.
#

from xml.dom import minidom
import urllib
import os
import time
import hashlib
from ConfigParser import SafeConfigParser
import re
import socket
#from urllib2 import Request, urlopen, quote
import urllib2
import base64
import uuid
import platform
from time import gmtime, strftime
import random
import string
from myplex import myPlexSignin
import traceback,sys

parser = SafeConfigParser()
parser.read('user.ini')

import subprocess

webstatus = parser.get('webui','status')
webport = parser.get('webui','port')
if webstatus=="enable":
    print "Starting PlexDownloader Web Manager..."
    subprocess.Popen(["python", "webui.py", webport])

print "Starting Plex Scraper..."
subprocess.Popen(["python", "scrape.py"])

sleepTime = parser.get('general', 'sleeptime')
sleepTime = int(sleepTime)
url = parser.get('general', 'plexurl')

myplexstatus = parser.get('myplex', 'status')
myplexusername = parser.get('myplex', 'username')
myplexpassword = parser.get('myplex', 'password')

pictureid = parser.get('pictures', 'plexid')
picturelocation = parser.get('pictures', 'picturelocation')
picturefile = parser.get('pictures', 'picturefile')
picturesync = parser.get('pictures', 'fullsync')
pictureactive = parser.get('pictures', 'active')

mimetypes = {   #Keep these all lowercase!
    'application/x-mpegurl':'m3u8',
    'application/vnd.apple.mpegurl':'m3u8',
    'application/octet-stream':'m2ts',
    'application/dash+xml':'mpd',
    'text/xml':'xml',

    'video/3gpp':'3gp',
    'video/avi':'avi',
    'video/mp2t':'ts',
    'video/mp4':'mp4',
    'video/mpeg':'mpeg',
    'video/ogg':'ogv',
    'video/quicktime':'mov',
    'video/x-flv':'flv',
    'video/x-matroska':'mkv',
    'video/x-msvideo':'avi',
    'video/x-ms-wmv':'wmv',
    'video/webm':'webm',

    'image/jpeg':	'jpg',
    'image/x-ms-bmp':'bmp',
    'image/gif':	'gif',
    'image/vnd.microsoft.icon':	'ico',
    'image/ief':	'ief',
    'image/x-portable-bitmap':	'pbm',
    'image/x-portable-graymap':	'pgm',
    'image/png':	'png',
    'image/x-portable-anymap':	'pnm',
    'image/x-portable-pixmap':	'ppm',
    'image/x-cmu-raster':	'ras',
    'image/x-rgb':	'rgb',
    'image/tiff':	'tiff',
    'image/x-xbitmap':	'xbm',
    'image/x-xpixmap':	'xpm',
    'image/x-xwindowdump':	'xwd',
    'image/jpg':	'jpg',
    'image/pict':	'pic',

    'audio/aac':    'aac',
    'audio/mp4':    'm4a',
    'audio/mpeg':   'mp3',
    'audio/ogg':    'oga',
    'audio/wav':    'wav',
    'audio/webm':   'webm',
    'audio/x-pn-realaudio':'ra',
    'application/x-pn-realaudio':'ram',
    'audio/basic':  'snd',
    'audio/x-wav':  'wav'
    }
subtitle_exts = ['srt', 'idx', 'sub', 'ssa', 'ass']
info_exts = ['nfo']
video_exts = ['3g2', '3gp', '3gp2', 'asf', 'avi', 'divx', 'flv', 'm4v', 'mk2',
              'mka', 'mkv', 'mov', 'mp4', 'mp4a', 'mpeg', 'mpg', 'ogg', 'ogm',
              'ogv', 'qt', 'ra', 'ram', 'rm', 'ts', 'wav', 'webm', 'wma', 'wmv',
              'iso', 'm2ts','mpa','mpe']
pic_exts = ['bmp','gif','ico','ief','jpe','jpeg','jpg','pbm','pgm','png','pnm','ppm',
            'ras','rgb','tif','tiff','xbm','xpm','xwd','jpg','pct','pic','pict']
audio_exts = [ 'aac','asf','mp4','m4a','mp1','mp2','mp3','mpg','mpeg','oga','ogg','wav','webm',
               '.mp2','.mp3','.ra','.ram','.snd','.wav', '.wma']



#random_data = os.urandom(128)
#plexsession = hashlib.md5(random_data).hexdigest()[:16]
plexsession=str(uuid.uuid4())  #todo: hardcode this (see https://www.npmjs.com/package/plex-api)
socket.setdefaulttimeout(180)

debug_limitdld = False      #set to true during development to limit size of downloaded files
debug_outputxml = False     #output relevant XML when exceptions occur
debug_pretenddld = False     #set to true to fake downloading.  connects to Plex but doesn't save the file.
debug_pretendremove = False    #set to true to fake removing files
debug_plexurl = False        #set to true to output plex URL  (caution - will output Plex token)
verbose = 0

plextoken=""

print "PlexDownloader - v0.06"

class MovieDownloader(object):
    class NoConfig(Exception):
        pass
    def __init__(self, num):
        tc = "movietranscode"
        cfg = "movies"
        if num > 0:
            tc += str(num)
            cfg += str(num)

        if not parser.has_section(cfg) or not parser.has_section(tc):
            #print "MovieDownloader %d - aborting" % num
            raise MovieDownloader.NoConfig("No config section")

        self.transcodeactive = parser.get(tc,'active')
        self.height = parser.get(tc,'height')
        self.width = parser.get(tc,'width')
        self.bitrate = parser.get(tc,'maxbitrate')
        self.quality = parser.get(tc,'videoquality')

        self.plexid = parser.get(cfg, 'plexid')
        self.location = parser.get(cfg, 'movielocation')
        self.configfile = parser.get(cfg, 'moviefile')
        self.sync = parser.get(cfg, 'fullsync')
        self.active = parser.get(cfg, 'active')
        self.unwatched = parser.get(cfg,'unwatched')
        self.structure = parser.get(cfg,'folderstructure')
        #print "MovieDownloader %d - success" % num

    def isactive(self):
        if self.active == "enable": return True
        return False

    def search(self):
        fp = open(self.configfile,"r")
        wantedlist= fp.read().split("\n")
        fp.close()
        print str(len(wantedlist)-1) + " Movies Found in Your Wanted List..."
        xmldoc = minidom.parse(urllib.urlopen(constructPlexUrl("/library/sections/"+str(self.plexid)+"/all")))
        itemlist = xmldoc.getElementsByTagName('Video')
        print str(len(itemlist)) + " Total Movies Found"
        syncedItems = 0
        failedItems = 0
        for item in itemlist:
            title = item.attributes['title'].value
            title = re.sub(r'[^\x00-\x7F]+',' ', title)
            title = re.sub(r'\&','and', title)
            itemkey = item.attributes['key'].value
            try:
                year = item.attributes['year'].value
            except Exception as e:
                year="Unknown"
            try:
                #checks to see if view count node is available
                viewcount = item.attributes['viewCount'].value
            except Exception as e:
                #if fails to find viewCount will notify script that it can continue
                viewcount = "unwatched"
            #checks if user wants unwatched only
            if self.unwatched=="enable":
                if viewcount=="unwatched":
                    print title + " ("+year+") is unwatched..."
                else:
                    if verbose: print title + " ("+year+") is watched... skipping!"
                    continue
            itemname = title + " ("+year+")"
            if (itemname in wantedlist) or (self.sync=="enable"):
                try:
                    parts = getMediaContainerParts(itemkey)
                    if not parts or len(parts) == 0: continue
                    existingfile = self.exists(itemname,parts[0])
                    if existingfile:
                        if verbose: print title + " ("+year+") exists... skipping!"
                        continue
                    self.download(itemname,itemkey,parts)
                    syncedItems += 1
                except Exception as e:
                    failedItems += 1
                    print "Error syncing " + itemname + ".  Skipping..."
                    print(traceback.format_exc())
                    if debug_outputxml: print item.toprettyxml(encoding='utf-8')
            else:
                if verbose: print itemname + " Not Found in Wanted List."
        if syncedItems > 0 or failedItems > 0:
            print "Movie synch complete: %d downloaded  %d errors" % (syncedItems, failedItems)

    #checks if a movie exists.  Handles both self.structure choices
    #returns full path to file if it exists, None if it does not.
    #Note that this specifically will locate a "movie (year).pt1.mkv" file
    #regardless of what specific part is passed
    #Any valid video extension is considered found movie
    def exists(self, itemname,part):
        filepath=self.fullfilepath(itemname,part)
        folder=os.path.dirname(filepath)
        filename=os.path.basename(filepath)
        if os.path.isdir(folder):
            for f in os.listdir(folder):
                if f.startswith(filename) and os.path.isfile(os.path.join(folder,f)):
                    if isValidVideoFile(f):
                        return os.path.join(folder,f)
                    else:
                        #print "Located " + f + " but is invalid extension"
                        pass
        return None

    #Path format of "self.location/movie name (year)/videos"
    #"server" structure uses the foldername and filename of the Plex server"
    #"default" structure uses generated folder and filenames
    #returns full filepath.  makes it all filesystem name-safe
    def fullfilepath(self, itemname,part,numparts=0,container=None):
        if self.structure == "server":
            f = os.path.join(self.location, getFilesystemSafeName(part['foldername']), getFilesystemSafeName(os.path.splitext(part['filename'])[0]))
        else:
            f = os.path.join(self.location, getFilesystemSafeName(itemname), getFilesystemSafeName(itemname))
            if part and numparts>1:
                f=f+".pt"+str(part['num'])
        if container:
            f = f+"."+getFilesystemSafeName(container)
        return f

    def download(self,itemname,plexkey,parts):
        plexsession = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(16))
        #plexsession = "z9fja0pznf40anzd"
        for counter, part in enumerate(parts):
            if len(parts) > 1:
                msg = itemname +"... Part %d of %d" % (counter+1, len(parts))
            else:
                msg = itemname+"..."
            if "subtitle" in part:
                print "Downloading subtitle "+ msg
                link = constructPlexUrl(part['key'])
                if not retrieveMediaFile(link, self.fullfilepath(itemname,part,len(parts)),extension=part["container"],overwrite=False):
                    print "Subtitle file not downloaded"
            elif self.transcodeactive=="enable":
                print "Downloading transcode "+ msg
                link = getTranscodeVideoURL(plexkey,self.quality,self.width, self.height, self.bitrate,plexsession,plextoken,counter)
                if not retrieveMediaFile(link, self.fullfilepath(itemname,part,len(parts)),overwrite=False):
                    print "Video not transcoded"
            else:
                print "Downloading "+ msg
                link = constructPlexUrl(part['key'])
                ext = os.path.splitext(part['filename'])[1][1:] #override
                if not retrieveMediaFile(link, self.fullfilepath(itemname,part,len(parts)),extension=getFilesystemSafeName(ext),overwrite=False):
                    print "Video not downloaded"

class TvDownloader(object):
    class NoConfig(Exception):
        pass
    def __init__(self, num):
        tc = "tvtranscode"
        cfg = "tvshows"
        if num > 0:
            tc += str(num)
            cfg += str(num)

        if not parser.has_section(cfg) or not parser.has_section(tc):
            raise TvDownloader.NoConfig("No config section")

        self.transcodeactive = parser.get(tc,'active')
        self.height = parser.get(tc,'height')
        self.width = parser.get(tc,'width')
        self.bitrate = parser.get(tc,'maxbitrate')
        self.quality = parser.get(tc,'videoquality')

        self.plexid = parser.get(cfg, 'plexid')
        self.configfile = parser.get(cfg, 'tvfile')
        self.type = parser.get(cfg, 'tvtype')
        self.location = parser.get(cfg, 'tvlocation')
        self.sync = parser.get(cfg, 'fullsync')
        self.active = parser.get(cfg, 'active')
        self.delete = parser.get(cfg, 'autodelete')
        self.unwatched = parser.get(cfg,'unwatched')
        self.structure = parser.get(cfg,'folderstructure')
        #print "MovieDownloader %d - success" % num

    def isactive(self):
        if self.active == "enable": return True
        return False

    def search(self):
        fp = open(self.configfile,"r")
        wantedlist= fp.read().split("\n")
        fp.close()
        print str(len(wantedlist)-1) + " TV Shows Found in Your Wanted List..."
        xmldoc = minidom.parse(urllib.urlopen(constructPlexUrl("/library/sections/"+self.plexid+"/all")))
        itemlist = xmldoc.getElementsByTagName('Directory')
        print str(len(itemlist)) + " Total TV Shows Found"
        syncedItems = 0
        failedItems = 0
        removedItems = 0
        for item in itemlist:
            title = item.attributes['title'].value
            title = re.sub(r'[^\x00-\x7F]+',' ', title)
            title = re.sub(r'\&','and', title)
            itemkey = item.attributes['key'].value
            #safeitemname = getFilesystemSafeName(title)
            if (title in wantedlist) or (self.sync =="enable"):
                print title + " Found in Wanted List"
                xmlseason = minidom.parse(urllib.urlopen(constructPlexUrl(itemkey)))
                seasonlist = xmlseason.getElementsByTagName('Directory')
                #construct list of episodes to sync
                episodelist = []
                if (self.type=="all") or (self.type=="episode"):    #download everything
                    for season in seasonlist:
                        if season.hasAttribute('index'):   #skip "allSeasons"
                            episodeweb=urllib.urlopen(constructPlexUrl(season.attributes['key'].value))
                            xmlepisode = minidom.parse(episodeweb)
                            for e in xmlepisode.getElementsByTagName('Video'):
                                e.setAttribute('seasonIndex', season.attributes['index'].value)
                                episodelist.append(e)
                elif (self.type=="recent"): #download latest season
                    episodeweb=urllib.urlopen(constructPlexUrl(seasonlist[len(seasonlist)-1].attributes['key'].value))
                    xmlepisode = minidom.parse(episodeweb)
                    for e in xmlepisode.getElementsByTagName('Video'):
                        e.setAttribute('seasonIndex', seasonlist[len(seasonlist)-1].attributes['index'].value)
                        episodelist.append(e)
                for counter, episode in enumerate(episodelist):
                    try:
                        episodekey = episode.attributes['key'].value
                        episodeindex = episode.attributes['index'].value
                        episodetitle = episode.attributes['title'].value
                        seasonindex = episode.attributes['seasonIndex'].value  #Added during list creation
                        #check if this already exists
                        try:
                            #checks to see if episode has been viewed node is available
                            viewcount = episode.attributes['lastViewedAt'].value
                        except Exception as e:
                            #if fails to find lastViewedAt will notify script that tv is unwatched
                            viewcount = "unwatched"
                        #checks if user wants unwatched only
                        if self.unwatched=="enable":
                            if viewcount=="unwatched":
                                if verbose: print "Episode is unwatched..."
                            else:
                                if verbose: print "Episode is watched... skipping!"
                                continue
                        parts = getMediaContainerParts(episodekey)
                        if not parts or len(parts) == 0: continue
                        if self.type=="episode" and (counter != len(episodelist)-1):
                            if self.delete=="enable":
                                #clean-up old episodes
                                #this logic isn't perfect.  It will not delete files that have been removed from the server.
                                fn = self.exists(title,seasonindex,episodeindex,parts[0])
                                if fn:
                                    try:
                                        print "Deleting old episode: " + fn
                                        if not debug_pretendremove: os.remove(fn)
                                        removedItems += 1
                                    except Exception as e:
                                        failedItems += 1
                                        print "Could not delete old episode. Will try again on the next scan."
                            continue
                        if self.exists(title,seasonindex,episodeindex,parts[0]):
                            if verbose: print title + " Season "+ seasonindex + " Episode " + episodeindex + " exists... skipping!"
                            continue
                        #print title + " Season "+ seasonindex + " Episode " + episodeindex
                        self.download(title,seasonindex,episodeindex,episodetitle,episodekey,parts)
                        syncedItems += 1
                    except Exception as e:
                        failedItems += 1
                        print "Error syncing episode.  Skipping..."
                        print(traceback.format_exc())
                        if debug_outputxml: print episode.toprettyxml(encoding='utf-8')
            else:
                print title + " Not Found in Wanted List."
        if syncedItems > 0 or failedItems > 0 or removedItems > 0:
            print "TV synch complete: %d downloaded, %d removed, %d errors" % (syncedItems, removedItems, failedItems)

    #checks if a tv episode exists based on season/episode.  Handles both self.structure choices
    #returns full path to file if it exists, None if it does not
    #Note that this specifically will locate a "show[*].pt1.mkv" file
    #regardless of what specific part is passed
    #Any valid video extension is considered found
    def exists(self,itemname,season,episode,part):
        season=int(season)
        episode=int(episode)
        #in server mode be strict about what to match against. Must be exactly the same.
        if self.structure == "server":
            filepath=self.fullfilepath(itemname,season,episode,"", part)
            folder=os.path.dirname(filepath)
            filename=os.path.basename(filepath)
            if os.path.isdir(folder):
                for f in os.listdir(folder):
                    if f.startswith(filename) and os.path.isfile(os.path.join(folder,f)):
                        if isValidVideoFile(f):
                            return os.path.join(folder,f)
                        else:
                            #print "Located " + f + " but is invalid extension"
                            pass
            return None
        #Be more flexible with searching for existing shows.
        dirs = []
        dirs.append(os.path.join(self.location,getFilesystemSafeName(itemname)))
        #also handle s1e01-e04 format
        pattern = '(?ix)(?:s)?(\d{1,3})(?:e|x)(\d{1,3})(?:-[ex](\d{1,3}))?(?:[\s\.\-,_])'  #handle where it just starts with S01
        r = re.compile(pattern)
        for folder in dirs:
            if os.path.isdir(folder):
                for f in os.listdir(folder):
                    result = r.search(f)
                    if result and os.path.isfile(os.path.join(folder,f)) and isValidVideoFile(f):
                        if episode == int(result.groups()[1]):
                            return os.path.join(folder,f)
                        if result.groups()[2]: # process s1e01-e04 files
                            #print result.groups()
                            if episode >= int(result.groups()[1]) and episode <= int(result.groups()[2]):
                                return os.path.join(folder,f)
        return None

    #"server" structure uses the foldername and filename of the Plex server"
    #"default" structure is "self.location/show name/episodes"
    #contents of part are used to determine if there should be a "ptX" appended
    #returns full filepath.  makes it all filesystem name-safe
    def fullfilepath(self,itemname,season,episode,eptitle,part,container=None):
        if self.structure == "server":
            f = os.path.join(self.location, getFilesystemSafeName(itemname), getFilesystemSafeName(part['foldername']), getFilesystemSafeName(os.path.splitext(part['filename'])[0]))
        else:
            f = os.path.join(self.location, getFilesystemSafeName(itemname), getFilesystemSafeName(itemname+" - s"+season+"e"+episode+" - "+eptitle))
            if part and int(part['num']) > 1:
                f=f+".pt"+str(part['num'])
        if container:
            f = f+"."+getFilesystemSafeName(container)
        return f

    def download(self,itemname,season,episode,eptitle,plexkey,parts):
        plexsession = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(16))
        #plexsession = "z9fja0pznf40anzd"
        for counter, part in enumerate(parts):
            eptitle = getFilesystemSafeName(eptitle)
            #if self.transcodeactive=="enable": msg = "transcoded"
            if len(parts) > 1:
                msg = itemname + " Season "+season+" Episode "+episode+"... Item %d of %d" % (counter+1, len(parts))
            else:
                msg = itemname + " Season "+season+" Episode "+episode+"..."
            if "subtitle" in part:
                print "Downloading subtitle "+ msg
                link = constructPlexUrl(part['key'])
                if not retrieveMediaFile(link, self.fullfilepath(itemname,season,episode,eptitle,part),extension=part["container"],overwrite=False):
                    print "Subtitle file not downloaded"
            elif self.transcodeactive=="enable":
                print "Downloading transcode "+ msg
                link = getTranscodeVideoURL(plexkey,self.quality,self.width, self.height, self.bitrate,plexsession,plextoken,counter)
                if not retrieveMediaFile(link, self.fullfilepath(itemname,season,episode,eptitle,part),overwrite=False):
                    print "Video file not transcoded"
            else:
                print "Downloading "+ msg
                link = constructPlexUrl(part['key'])
                ext = os.path.splitext(part['filename'])[1][1:] #override extension
                if not retrieveMediaFile(link, self.fullfilepath(itemname,season,episode,eptitle,part),extension=getFilesystemSafeName(ext),overwrite=False):
                    print "Video file not downloaded"

    # def getSeasonAndEpisodeFromFilename(filename):
    #     #todo: Add in syntax below for multi-episode formats
    #     m = re.findall(r"(?ix)(?:[\s\.\-,_])(?:s)(\d{1,3})(?:e|x)(\d{1,3})", filename, re.I)   #s1e1,s1x1
    #     if not m:
    #         m = re.findall(r"(?ix)(?:[\s\.\-,_])(\d{1,3})(?:e|x)(\d{1,3})", filename, re.I)  #1e1,1x1
    #     return (int(m[0][0]),int(m[0][1]))  #returns integer version of just the first match in the filename

    #checks if a tv episode exists based on season/episode.  Handles both tvstructure choices
    #returns full path to file if it exists, None if it does not
    #Note that this specifically will locate a "show[*].pt1.mkv" file
    #regardless of what specific part is passed
    #Any valid video extension is considered found
    #NOT USED RIGHT NOW.  ARCHIVED FOR USE LATER
    # def tvEpisodeExistsFlex(show,season,episode):
    #     dirs = []
    #     season=int(season)
    #     episode=int(episode)
    #     if tvstructure == "server":
    #         dirs.append(os.path.join(tvlocation, show, "Season "+str(season).zfill(1)))
    #         dirs.append(os.path.join(tvlocation, show, "Season "+str(season).zfill(2)))
    #         dirs.append(os.path.join(tvlocation, show, "Season "+str(season).zfill(3)))
    #         if season == 0:
    #             dirs.append(os.path.join(tvlocation, show, "Specials"))
    #     else:
    #         dirs.append(os.path.join(tvlocation,show))
    #     #pattern = '(?ix)(?:[\s\.\-,_])(?:s)?(\d{1,3})(?:e|x)(\d{1,3})(?:-[ex](\d{1,3}))?(?:[\s\.\-,_])'
    #     #also handle s1e01-e04 format
    #     pattern = '(?ix)(?:s)?(\d{1,3})(?:e|x)(\d{1,3})(?:-[ex](\d{1,3}))?(?:[\s\.\-,_])'  #handle where it just starts with S01
    #     r = re.compile(pattern)
    #     for folder in dirs:
    #         if os.path.isdir(folder):
    #             for f in os.listdir(folder):
    #                 result = r.search(f)
    #                 if result and isValidVideoFile(f):
    #                     if episode == int(result.groups()[1]):
    #                         return os.path.join(folder,f)
    #                     if result.groups()[2]: # process s1e01-e04 files
    #                         #print result.groups()
    #                         if episode >= int(result.groups()[1]) and episode <= int(result.groups()[2]):
    #                             return os.path.join(folder,f)
    #     return None

class MusicDownloader(object):
    class NoConfig(Exception):
        pass

    def __init__(self, num):
        cfg = "music"
        if num > 0:
            cfg += str(num)

        if not parser.has_section(cfg):
            raise MusicDownloader.NoConfig("No config section")

        self.plexid = parser.get(cfg, 'plexid')
        self.location = parser.get(cfg, 'musiclocation')
        self.configfile = parser.get(cfg, 'musicfile')
        self.sync = parser.get(cfg, 'fullsync')
        self.active = parser.get(cfg, 'active')

    def isactive(self):
        if self.active == "enable": return True
        return False

    def search(self):
        fp = open(self.configfile,"r")
        wantedlist= fp.read().split("\n")
        fp.close()
        print str(len(wantedlist)-1) + " Artists Shows Found in Your Wanted List..."
        xmldoc = minidom.parse(urllib.urlopen(constructPlexUrl("/library/sections/"+self.plexid+"/all")))
        itemlist = xmldoc.getElementsByTagName('Directory')
        print str(len(itemlist)) + " Total TV Artists Found"
        syncedItems = 0
        failedItems = 0
        for item in itemlist:
            title = item.attributes['title'].value
            title = re.sub(r'[^\x00-\x7F]+',' ', title)
            title = re.sub(r'\&','and', title)
            itemkey = item.attributes['key'].value
            if (title in wantedlist) or (self.sync =="enable"):
                try:
                    print title + " Found in Wanted List"
                    xmlseason = minidom.parse(urllib.urlopen(constructPlexUrl(itemkey)))
                    cdlist = xmlseason.getElementsByTagName('Directory')
                    for cd in cdlist:
                        cdtitle = cd.attributes['title'].value
                        if cd.hasAttribute('index'):   #skip "allSeasons"
                            xmlsong = minidom.parse(urllib.urlopen(constructPlexUrl(cd.attributes['key'].value)))
                            #Get List of Songs
                            songlist=xmlsong.getElementsByTagName('Track')
                            #Check for duplicate song titles
                            numberTitles = False
                            songnames = [s.attributes['title'].value for s in songlist]
                            if any(songnames.count(x) > 1 for x in songnames):
                                numberTitles = True
                                print "Warning: Duplicate song titles.  Adding track number at beginning of filename."
                            for counter,song in enumerate(songlist):
                                songtitle = song.attributes['title'].value
                                songrating = song.attributes['ratingKey'].value
                                if songtitle=="":
                                    songtitle = songrating
                                if numberTitles:
                                    if song.hasAttribute('index'):
                                        songtitle = str(song.attributes['index'].value).zfill(3) + " " + songtitle
                                    else:
                                        songtitle = str(counter).zfill(3) + " " + songtitle
                                parts = getMediaContainerParts(song.attributes['key'].value)
                                if not parts or len(parts) == 0: continue
                                if self.exists(title,cdtitle,songtitle,parts[0]):
                                    if verbose: print cdtitle + " / " +songtitle+" exists... skipping!"
                                    continue
                                self.download(title,cdtitle,songtitle,parts)
                                syncedItems += 1
                except Exception as e:
                    failedItems += 1
                    print "Error syncing " + title + ".  Skipping..."
                    print(traceback.format_exc())
                    if debug_outputxml: print item.toprettyxml(encoding='utf-8')
            else:
                print title + " Not Found in Wanted List."
        if syncedItems > 0 or failedItems > 0:
            print "Music synch complete: %d downloaded, %d errors" % (syncedItems, failedItems)

    #returns full filepath.  makes it all filesystem name-safe
    def fullfilepath(self,artist,cd,song,part,extension=None):
        f = os.path.join(self.location, getFilesystemSafeName(artist), getFilesystemSafeName(cd), getFilesystemSafeName(song))
        if part and int(part['num']) > 1:
            f=f+".pt"+str(part['num'])
        if extension:
            f = f+"."+extension
        return f

    def exists(self,artist,cd,song,part):
        filepath=self.fullfilepath(artist,cd,song,part)
        folder=os.path.dirname(filepath)
        filename=os.path.basename(filepath)
        if os.path.isdir(folder):
            for f in os.listdir(folder):
                if f.startswith(filename) and os.path.isfile(os.path.join(folder,f)):
                    if isValidAudioFile(f):
                        return os.path.join(folder,f)
                    else:
                        #print "Located " + f + " but is invalid extension"
                        pass
        return None

    def download(self,artist,cd,song,parts):
        for counter, part in enumerate(parts):
            if len(parts) > 1:
                msg = cd + " Song: "+song+"..."+"... Part %d of %d" % (counter+1, len(parts))
            else:
                msg = cd + " Song: "+song+"..."
            #this is good for both audio files and any future subtitles (future-proof for lyrics)
            print "Downloading "+ msg
            link = constructPlexUrl(part['key'])
            ext = part['container']  #use whatever the server said it is first
            if not ext: ext = os.path.splitext(part['filename'])[1][1:]
            if not retrieveMediaFile(link, self.fullfilepath(artist,cd,song,part),extension=getFilesystemSafeName(ext),overwrite=False):
                print "Music file not downloaded"



def isValidVideoFile(filename):
    try:
        ext = os.path.splitext(filename)[1].lower()[1:]
        if ext in video_exts:
            return True
        return False
    except Exception as e:
        #print(traceback.format_exc())
        return False

def isValidAudioFile(filename):
    try:
        ext = os.path.splitext(filename)[1].lower()[1:]
        if ext in audio_exts:
            return True
        return False
    except Exception as e:
        #print(traceback.format_exc())
        return False

def getTranscodeVideoURL(plexkey,quality,width,height,bitrate,session,token,partindex=0):
    clientuid = uuid.uuid4()
    clientid = clientuid.hex[0:16]
    link = (url+"/video/:/transcode/universal/start?path=http%3A%2F%2F127.0.0.1%3A32400"+plexkey+
            "&mediaIndex=0"+
            "&partIndex="+str(partindex)+
            "&protocol=http"+
            "&offset=0"+
            "&fastSeek=1"+
            "&directPlay=0"+
            "&directStream=1"+
            "&videoQuality="+quality+
            "&videoResolution="+width+"x"+height+
            "&maxVideoBitrate="+bitrate+
            "&subtitleSize=100"+
            "&audioBoost=100"+
            "&session="+session+
            #"&X-Plex-Client-Profile-Extra=add-transcode-target-audio-codec(type%3DvideoProfile%26context%3Dstreaming%26protocol%3Dhls%26audioCodec%3Daac)"+  #restrict audiocodec to aac
            "&X-Plex-Client-Identifier="+clientid+
            "&X-Plex-Product=Plex Web"+
            "&X-Plex-Device=Plex Downloader"+
            "&X-Plex-Platform=HTML TV App"+
            "&X-Plex-Platform-Version=43.0"+
            "&X-Plex-Version=2.4.9"
            )
    if myplexstatus=="enable":
        link = link+"&X-Plex-Token="+token
    if debug_plexurl: print link
    return link

#hls flow



#Downloads link to file.  Will detect the type of video file and add the
#correct extension to file.  Will work with multi-part video files.
#Set extension to non-None to override the automatic detection
#Will overwrite existing files if "overwrite==True"
#Returns True on download, False on no-download or failure
def retrieveMediaFile(link,filename,extension=None,overwrite=False):
    try:
        #if verbose: print "storing link to: " + filename
        cleanup = False  #gracefully cleanup failed transcodes so we can try again
        if not os.path.exists(os.path.split(filename)[0]):
            os.makedirs(os.path.split(filename)[0])
        epfile = urllib.urlopen(link)
        print epfile.info()
        if not extension:
            mimetype = epfile.info().type.lower()
            mimetype = mimetype.replace('content-type: ','')  #plex has bug that returns "Content-Type" as part of the Content-Type.  Doh!
            if mimetype in mimetypes:
                extension = mimetypes[mimetype]
            else:
                print "Warning: Unknown mimetype for file (%s) Using mpg as default" % (mimetype)
                extension = "mpg"  #use this as default
        filename=filename+"."+extension.lower()
        #if verbose: print "Downloading "+link+" ==> "+filename
        if verbose: print "Downloading "+filename
        if debug_pretenddld: return True
        if overwrite or (not os.path.isfile(filename)):
            with open(filename, "wb") as fp:
                cleanup = True
                while True:
                    chunk = epfile.read(1024*1024)  #1MB buffer
                    if not chunk: break
                    fp.write(chunk)
                    if debug_limitdld: break   #for development. limit to a single buffer size for output
            return True
        else:
            #this shouldn't really happen much.  Existing files should be caught before file is downloaded.
            #Can happen when there is a new extension or when subtitles/multi-parts exist
            print "File already exists. Skipping download."
            return False
    except (KeyboardInterrupt, SystemExit):
        try:
            if cleanup: os.remove(filename)
        except:
            pass
        raise KeyboardInterrupt()
    except Exception as e:
        print "Something went wrong transcoding video... Deleting and retrying on next scan!"
        print "Something went wrong: " + str(e)
        print(traceback.format_exc())
        try:
            if cleanup: os.remove(filename)
        except:
            pass

    return False

def constructPlexUrl(key):
    http = str(url) + str(key)
    if myplexstatus=="enable":
        http +="?X-Plex-Token="+plextoken
    if debug_plexurl: print http
    return http

#Loads the passed key from node.
#'container' is sometimes None
def getMediaContainerParts(key):
    try:
        xmlmedia = minidom.parse(urllib.urlopen(constructPlexUrl(key)))
        partindex = xmlmedia.getElementsByTagName('Part')
        parts = []
        for counter, partitem in enumerate(partindex):
            downloadkey = partitem.attributes['key'].value  #key goes directly to file
            filepath = urllib.unquote(partitem.attributes['file'].value)
            #even on Linux, need to encode to cp1252 to handle extended characters
            filepath = filepath.encode("cp1252").decode("utf-8")
            filename = os.path.basename(filepath)
            foldername = os.path.dirname(os.path.realpath(filepath))
            foldername = os.path.basename(os.path.realpath(foldername))
            container = partitem.getAttribute('container')  #not always present
            parts.append({"num":counter+1, "key":downloadkey, "filename":filename,"foldername":foldername, "container":container})
            #Add any subtitle files
            try:  #seperate try block so failure is limited to subtitles (which can be messy)
                streamindex = partitem.getElementsByTagName('Stream')
                subtitles = {}
                #only 3 types of streams.  1=video, 2=audio, 3=subtitle
                for stream in streamindex:
                    if (stream.getAttribute("streamType") == "3") and (stream.getAttribute("key")):  #only streams with keys are non-embedded
                        if stream.getAttribute("codec").lower() in subtitle_exts:
                            lang = stream.getAttribute("languageCode").lower()
                            if not lang: lang = "unk"
                            if lang in subtitles:
                                streamcontainer = lang + "." + str(subtitles[lang]) + "." + stream.getAttribute("codec").lower()
                                subtitles[lang] += 1
                            else:
                                streamcontainer = lang + "." + stream.getAttribute("codec").lower()
                                subtitles[lang] = 1
                            parts.append({"num":counter+1, "key":stream.getAttribute("key"), "filename":filename,"foldername":foldername, "container":streamcontainer, "subtitle":True})
            except Exception as e:
                print "Error while getting subtitles"
                print(traceback.format_exc())
        return parts
    except Exception as e:
        print "Error while getting media parts"
        print(traceback.format_exc())
        return None

def getFilesystemSafeName(s):
    s = re.sub(r'[\\/:"*?<>|"]+',"",s)
    return s

def photoDownloader(albumname,picturename,link,container):
    photofile=urllib.URLopener()
    albumname = getFilesystemSafeName(albumname)
    picturename = getFilesystemSafeName(picturename)

    if not os.path.exists(picturelocation+albumname):
        os.makedirs(picturelocation+albumname)

    print "Downloading Album: "+ albumname + " Picture: " +picturename +" ..."

    if not os.path.isfile(picturelocation+albumname+"/"+picturename+"."+container):
        try:
            photofile.retrieve(link,picturelocation+albumname+"/"+picturename+"."+container)
        except Exception as e:
            print "Something went wrong downloading this picture... Deleting and retrying on next picture scan!"
            os.remove(picturelocation+albumname+"/"+picturename+"."+container)
    else:
        print "File already exists. Skipping picture."


def photoSearch():
    pictureopen = open(picturefile,"r")
    pictureread = pictureopen.read()
    picturelist= pictureread.split("\n")
    pictureopen.close()
    print str(len(picturelist)-1) + " Albums Found in Your Wanted List..."

    if myplexstatus=="enable":
        pichttp=url+"/library/sections/"+pictureid+"/all"+"?X-Plex-Token="+plextoken
    else:
        pichttp=url+"/library/sections/"+pictureid+"/all"
    website = urllib.urlopen(pichttp)
    xmldoc = minidom.parse(website)
    itemlist = xmldoc.getElementsByTagName('Directory')
    print str(len(itemlist)) + " Total Albums Found"
    for item in itemlist:
        albumtitle = item.attributes['title'].value
        albumtitle = re.sub(r'[^\x00-\x7F]+',' ', albumtitle)
        albumtitle = re.sub(r'\&','and', albumtitle)
        albumkey = item.attributes['key'].value
        #checks if album is in your wanted list or if full sync is enabled
        if (albumtitle in picturelist) or (picturesync=="enable") :
            if myplexstatus=="enable":
                albumhttp=url+albumkey+"?X-Plex-Token="+plextoken
            else:
                albumhttp=url+albumkey
            albumweb=urllib.urlopen(albumhttp)
            xmlalbum=minidom.parse(albumweb)
            picturesinalbum=xmlalbum.getElementsByTagName('Photo')
            for pics in picturesinalbum:

                pictitle= pics.attributes['title'].value
                partalbum=pics.getElementsByTagName('Part')

                piccontainer = partalbum[0].attributes['container'].value
                pickey = partalbum[0].attributes['key'].value

                if myplexstatus=="enable":
                    piclink=url+pickey+"?X-Plex-Token="+plextoken
                else:
                    piclink=url+pickey
                print pictitle + albumtitle
                photoDownloader(albumtitle,pictitle,piclink,piccontainer)

        else:
            print albumtitle + " Album Not Found in Wanted List."


#Load all sections from config file
movies = []
try:
    while True: movies.append(MovieDownloader(len(movies)))
except MovieDownloader.NoConfig: pass
tvshows = []
try:
    while True: tvshows.append(TvDownloader(len(tvshows)))
except TvDownloader.NoConfig: pass
music = []
try:
    while True: music.append(MusicDownloader(len(music)))
except MusicDownloader.NoConfig: pass

while True:
    try:
        if myplexstatus=="enable":
            plextoken = myPlexSignin(myplexusername,myplexpassword)
        if myplexstatus=="enable" and plextoken=="":
            print "Failed to login to myPlex. Please disable myPlex or enter your correct login."
            exit()
        for x in tvshows:
            if(x.isactive()):
                x.search()
        for x in movies:
            if(x.isactive()):
                x.search()
        for x in music:
            if(x.isactive()):
                x.search()
        if pictureactive=="enable":
            photoSearch()

        print "Plex Download completed at "+ strftime("%Y-%m-%d %H:%M:%S")
        print "Sleeping "+str(sleepTime)+" Seconds..."
        time.sleep(sleepTime)
    except Exception as e:
        print "Something went wrong: " + str(e)
        print(traceback.format_exc())
        print "Plex Download failed at "+ strftime("%Y-%m-%d %H:%M:%S")
        print "Retrying in "+str(sleepTime)+" Seconds..."
        time.sleep(sleepTime)
