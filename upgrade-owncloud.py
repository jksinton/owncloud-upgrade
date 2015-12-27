#!/usr/bin/python

#*******************************************************************************
#*******************************************************************************
# 
#                      COPYRIGHT (c) 2015, James Sinton
#                             ALL RIGHTS RESERVED
# 
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 2.1 of the License, or (at your option) any later version.
# 
#  This library is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
# 
#   DESCRIPTION
#      This script will upgrade owncloud
# 
#   EXAMPLES
#      sudo ugrade-owncloud.py --code oc.tar.gz
# 
#      sudo ugrade-owncloud.py
#   
#   AUTHOR
#      James Sinton
# 
#********************************************************************************
#********************************************************************************
# 
#   CHANGE LOG
#   09-02-2015  Initial creation and design framework                     - 0.1.0
#   09-07-2015  Checks if an update is available from owncloud.com        - 0.1.1
#   09-08-2015  Converted most subrpocess commands to standard Python     - 0.1.2
#               libraries             
#   09-11-2015  Json encode version.php                                   - 0.1.3
#   09-12-2015  Reads config.php to get data path and db parameters       - 0.1.4
#   09-25-2015  Converting to class structure                             - 0.1.5
# 
#********************************************************************************
#********************************************************************************

import argparse
import datetime
import glob
import gzip
import httplib
import json
import os
import shutil
import subprocess
import tarfile
import urllib2
import xml.etree.ElementTree as ET
import zipfile
from pwd import getpwnam

##################################################################
#Class Name:    ownCloud
#Parameters:    none
#Purpose:       Stores ownCloud parameters and run installation
##################################################################
class ownCloud():
    def __init__(self):
        ocDir='owncloud'
        dataDir='data'
        self.wwwUser='www-data' # Set wwwUser to the user running your web server, e.g., www-data on Ubuntu
        self.wwwPath='/var/www' # Set wwwPath to the path where your root http files are hosted, i.e. where ownCloud is installed
        self.backupPath='/var/owncloud.bak' # Set backupPath to the path where backups will be stored
        self.ocPath=self.wwwPath + '/' + ocDir
        self.dataPath=self.wwwPath + '/' + dataDir
        self.backupTime=datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')
        self.dbType=None
        self.dbName=None
        self.dbUser=None
        self.dbPassword=None
        self.updateIsAvalable=False
        self.ocVersion=None
        self.ocVersionString=None
        self.backupDir=None
        self.backupDB=None
        self.upgradeCodeFileName=None
        self.updateURL=None
        self.updateVersionString=None

    ##################################################################
    #Function Name: getOCVersion
    #Parameters:    self
    #Purpose:       Set current version of ownCloud installed in
    #               version.php
    #		    @checkUpdate
    ##################################################################
    def getOCVersion(self):
        print "\nGetting current version of ownCloud that is installed . . ."
        vFileName=self.ocPath +'/version.php'
        cmd=['/usr/bin/php','-r','include "'+vFileName+'"; echo json_encode(array($OC_Version,$OC_VersionString));']
        self.ocVersion, self.ocVersionString=json.loads(subprocess.check_output(cmd))
        print "Current Version Installed:  " + self.ocVersionString

    ##################################################################
    #Function Name: getOCconfig
    #Parameters:    self
    #Purpose:       Return config parameters
    #		    @checkUpdate
    ##################################################################
    def getOCConfig(self):
        print "\nGetting database parameters and path to 'data' . . ."
        cFileName=self.ocPath + '/config/config.php'
        cmd=['/usr/bin/php','-r','include "'+cFileName+'"; echo json_encode($CONFIG);']
        c=json.loads(subprocess.check_output(cmd))
        self.dataPath=c['datadirectory']
        self.dbType=c['dbtype']
        self.dbName=c['dbname']
        self.dbUser=c['dbuser']
        self.dbPassword=c['dbpassword']

    ##################################################################
    #Function Name: checkUpdate
    #Parameters:    self
    #Purpose:       check if an update is available
    #               @main
    ##################################################################
    def checkUpdate(self):
        # Exmample url syntax to query owncloud.com for update:
        # https://apps.owncloud.com/updater.php?version=8x0x6x2xxxstablexx
        secureHost="apps.owncloud.com"
        version = 'x'.join([str(i) for i in self.ocVersion])
        #version = '8x0x6x2'
        url="/updater.php?version=" +version+ "xxxstablexx"
        print '\nChecking to see if an update is available using:\n\thttps://' + secureHost + url
        connection = httplib.HTTPSConnection(secureHost)
        connection.request("GET",url)
        response = connection.getresponse()
        print "\nResponse status from owncloud.com:  "
        print response.status, response.reason
        data=response.read()
        print "\nownCloud.com returned this XML:"
        print data
        xml = ET.fromstring(data)
        print "Reading the XML data . . ." 
        for element in xml.iter('versionstring'):
            if element.text is not None:
                updateVersionString=element.text
                self.updateVersionString=updateVersionString
                print "\t" +element.text + " is available."
        for element in xml.iter('url'):
            if element.text is not None:
                updateURL=element.text
                print "\tCode:\t\t" + updateURL
                self.updateURL=updateURL
                self.updateIsAvailable = True
            else:
                self.updateIsAvailable = False
        for element in xml.iter('web'):
            if element.text is not None:
                print "\tInstructions:\t" + element.text

    ##################################################################
    #Function Name: backupOC
    #Parameters:    self
    #Purpose:       backup ownCloud
    #		    @main
    ##################################################################
    def backupOC(self):
        self.backupDir=self.backupPath + '/oc_' + self.ocVersionString + '_' + self.backupTime
        self.backupDB=self.backupPath + '/owncloud_' + self.ocVersionString + '_' + self.backupTime +'.sql'
    
        # place owncloud server into maintenance mode
        print "\n"
        print "Placing owncloud server into maintainance mode..."
        cmd = ['sudo','-u',self.wwwUser, '/usr/bin/php', self.ocPath + '/occ', 'maintenance:mode', '--on']
        out, err = subprocess.Popen(cmd,stdout=subprocess.PIPE, stderr=subprocess.PIPE ).communicate()
        print out
    
        # backup owncloud installation
        print "\n"
        print "Backing up owncloud code . . ."
        print "\tcopying old code to backup directory"
        shutil.copytree(self.ocPath,self.backupDir)
        print "\tresetting secure permssions across backup"
        securePermissions(self.backupDir,self.wwwUser,None)
         
        # backup owncloud database
        print "\n"
        print "Backing up owncloud database . . ."
        cmd = ['sudo','mysqldump','--result-file='+self.backupDB,'-u',self.dbUser, '--password='+self.dbPassword, self.dbName]
        out, err = subprocess.Popen(cmd,stdout=subprocess.PIPE, stderr=subprocess.PIPE ).communicate()
        print out
    
        with open(self.backupDB,'rb') as backupDB, gzip.open(self.backupDB + '.gz','wb') as gzipDB:
            shutil.copyfileobj(backupDB,gzipDB)
        backupDB.close()
        gzipDB.close()
        # remove backupDB
        try:
            os.remove(self.backupDB)
        except OSError, e:
            print ("Error:  %s - %s." % (e.filename,e.strerror))

    ##################################################################
    #Function Name: checkOCVersion
    #Parameters:    self
    #Purpose:       Check if current version of ownCloud installed
    #               differs from previous version installed
    #		    @installUpgrade
    ##################################################################
    def checkOCVersion(self):
        vFileName=self.ocPath+'/version.php'
        cmd=['/usr/bin/php','-r','include "'+vFileName+'"; echo json_encode(array($OC_Version,$OC_VersionString));']
        ocVersion, ocVersionString=json.loads(subprocess.check_output(cmd))
        print "\n"
        print "Previous Version Installed:  " + self.ocVersionString
        print "Current Version Installed:  " + ocVersionString
        if ocVersion != self.ocVersion:
            print "\n"
            print "The versions do not match."
            print "Installation seems to be successful.  You may proceed with upgrade . . ."
            return True
        else:
            print "The versions match."
            print "Installation failed.  You should fix this then proceed with upgrade . . ."
            return False

    ##################################################################
    #Function Name: installUpgrade
    #Parameters:    self
    #Purpose:       Install upgrade code
    #	      	    @main
    ##################################################################
    def installUpgrade(self):
        # stopping web server
        print "\n"
        print "Stopping web server"
        cmd = ['sudo','service','apache2', 'stop']
        out, err = subprocess.Popen(cmd,stdout=subprocess.PIPE, stderr=subprocess.PIPE ).communicate()
        print out

        print "\n"
        print "Setting up new release for installation . . ."
        
        if self.upgradeCodeFileName is None and self.updateURL is not None:
            # download new release
            codeFileName=self.wwwPath + '/'+self.updateURL.split('/')[-1]
            downloadFile(self.updateURL,codeFileName)
        else:
            codeFileName=self.upgradeCodeFileName

        if tarfile.is_tarfile(codeFileName): 
            try:
                shutil.rmtree(self.ocPath)
            except OSError, e:
                print ("Error:  %s - %s." % (e.filename,e.strerror))
            extractall(codeFileName,self.wwwPath+'/')
        elif zipfile.is_zipfile(codeFileName):
            try:
                shutil.rmtree(self.ocPath)
            except OSError, e:
                print ("Error:  %s - %s." % (e.filename,e.strerror))
            extractall(codeFileName,self.wwwPath+'/')
        else:
            print codeFileName + " does not seem to be a tarball or a zip file."
            return False

        # Restoring config.php
        if os.path.isfile(self.backupDir+'/config/config.php'):
            print "\n"
            print "Restoring config.php"
            shutil.copy(self.backupDir+'/config/config.php',self.ocPath+'/config/config.php')
        else:
            print "You must restore config.php before running occ upgrade script; no backup was found in "+self.backupDir
    
        # Setting secure permissions
        print "\n"
        print "Setting secure permissions . . ."
        securePermissions(self.ocPath,self.wwwUser,self.dataPath)

        # stopping web server
        print "\n"
        print "Starting web server"
    
        cmd = ['sudo','service','apache2', 'start']
        out, err = subprocess.Popen(cmd,stdout=subprocess.PIPE, stderr=subprocess.PIPE ).communicate()
        print out
    
        # Check version
        if self.checkOCVersion():
            # Ask whether you want to run the upgrade script
            question="Please check that updated code has been correctly installed in "+self.ocPath+".\nDo you want to run the occ upgrade script?"
            if askYesorNo(question,"yes") is "yes":
                # Upgrade owncloud
                print "\n"
                print "Upgrading owncloud . . ."
                cmd = ['sudo','-u',self.wwwUser, '/usr/bin/php', self.ocPath+'/occ', 'upgrade']
                out, err = subprocess.Popen(cmd,stdout=subprocess.PIPE, stderr=subprocess.PIPE ).communicate()
                print out
    
                # Disable maintenance mode
                print "\n"
                print "Taking owncloud online"
                cmd = ['sudo','-u',self.wwwUser, '/usr/bin/php', self.ocPath+'/occ', 'maintenance:mode', '--off']
                out, err = subprocess.Popen(cmd,stdout=subprocess.PIPE, stderr=subprocess.PIPE ).communicate()
                print out
    
                print "Installation is complete . . ."

##################################################################
#Function Name: getArgs
#Parameters:    none
#Purpose:       Define command line arguments and return them to 
#		main
#		@main
##################################################################
def getArgs():
    version='0.1.5'
    parser = argparse.ArgumentParser(description='This upgrades owncloud.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-c','--code',help='tarball of new code')
    group.add_argument('--check',help='check for update',action="store_true")
    group.add_argument('--install',help='check for update, download it, install it',action="store_true")
    group.add_argument('-b','--backup',help='backup owncloud',action="store_true")
    parser.add_argument('--no-backup',help='do not backup owncloud',action="store_true")
    parser.add_argument('-f','--force-install',help='answers yes to everything',action="store_true")
    parser.add_argument('-v','--version',action='version', version='%(prog)s %(version)s' % {"prog": parser.prog, "version": version})
    parser.add_argument('-d','--debug',help='print debug messages',action="store_true")

    return parser.parse_args()

##################################################################
#Function Name: chownR
#Parameters:    path, uid, gid
#Purpose:       Recursively change owner
#		@securePermissions
##################################################################
def chownR(path,uid=-1,gid=-1):
    print path
    if os.path.isdir(path)==False:
        print "\tMaking "+ path
        os.mkdir(path)
    os.chown(path,uid,gid)
    for root, dirnames, filenames in os.walk(path):
        for direc in dirnames:
            #print os.path.join(root,direc)
            os.chown(os.path.join(root,direc),uid,gid)
        for f in filenames:
            #print os.path.join(root,f)
            os.chown(os.path.join(root,f),uid,gid)

##################################################################
#Function Name: securePermissions
#Parameters:    None
#Purpose:       Set secure permissions for installation
#		@installUpgrade
##################################################################
def securePermissions(path='/var/www/owncloud',wwwUser='www-data',dataPath='/var/www/owncloud/data'):
    rootUID=getpwnam('root').pw_uid
    wwwUID=getpwnam(wwwUser).pw_uid
    wwwGID=getpwnam(wwwUser).pw_gid
    chownR(path,rootUID,wwwGID)
    os.chmod(path, 0750)
    chownR(path+'/apps/',wwwUID,wwwGID)
    chownR(path+'/config/',wwwUID,wwwGID)
    chownR(path+'/themes/',wwwUID,wwwGID)
    for root, dirnames, filenames in os.walk(path):
        for direc in dirnames:
            #print os.path.join(root,direc)
            os.chmod(os.path.join(root,direc), 0750)
        for f in filenames:
            #print os.path.join(root,f)
            os.chmod(os.path.join(root,f), 0640)
    if os.path.exists(path+'/.htaccess'):
        os.chmod(path+'/.htaccess', 0640)
    if dataPath is not None:
        chownR(dataPath,wwwUID,wwwGID)
        if os.path.exists(dataPath+'/.htaccess'):
            os.chmod(dataPath +'/.htaccess', 0640)

##################################################################
#Function Name: copytree
#Parameters:    src, dst, symlinks=False, ignore=None 
#Purpose:       
#		@backupOC, intstallUpgrade
##################################################################
def copytree(src, dst, symlinks=False, ignore=None):
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, symlinks, ignore)
        else:
            shutil.copy2(s, d)

##################################################################
#Function Name: downloadFile
#Parameters:    url, dlFileName
#Purpose:       returns fileObject
#		@installUpgrade
##################################################################
def downloadFile(url,dlFileName):
    urlObject=urllib2.urlopen(url)
    dlFileObject=open(dlFileName,'wb')
    meta = urlObject.info()
    fileSize = int(meta.getheaders("Content-Length")[0])
    print "Downloading: %s Bytes: %s" % (dlFileName.split('/')[-1], fileSize)
    
    fileSizeDL = 0
    blockSize = 8192
    while True:
        buffer = urlObject.read(blockSize)
        if not buffer:
            break

        fileSizeDL += len(buffer)
        dlFileObject.write(buffer)
        status = r"%10d  [%3.2f%%]" % (fileSizeDL, fileSizeDL * 100. / fileSize)
        status = status + chr(8)*(len(status)+1)
        print status,
    dlFileObject.close()

##################################################################
#Function Name: extractall
#Parameters:    fn, dst
#Purpose:       extracts archive to dst
#		@installUpgrade
##################################################################
def extractall(fn,dst="."):
    if tarfile.is_tarfile(fn): 
        with tarfile.open(fn,'r') as tf:
            tf.extractall(dst)
            tf.close()
    elif zipfile.is_zipfile(fn):
        with zipfile.ZipFile(fn, 'r') as zf:
            zf.extractall(dst)
            zf.close()
    else:
        print "Please provide a tar archive file or zip file containing the update."

##################################################################
#Function Name: askYesorNo
#Parameters:    question, default answer
#Purpose:       It asks a yes or no question and prompts the user
#		@main
##################################################################
def askYesorNo(question, default="yes"):
    """Ask a yes/no question via raw_input() and return their answer.
    
    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is one of "yes" or "no".
    """
    valid = {"yes":"yes",   "y":"yes",  "ye":"yes",
             "no":"no",     "n":"no"}
    if default == None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while 1:
        #sys.stdout.write(question + prompt)
        print(question + prompt)
        choice = raw_input().lower()
        if default is not None and choice == '':
            return default
        elif choice in valid.keys():
            return valid[choice]
        else:
            #sys.stdout.write("Please respond with 'yes' or 'no' "\
            print("Please respond with 'yes' or 'no' "\
                             "(or 'y' or 'n').\n")

##################################################################
#Function Name: main
#Parameters:    no
#Purpose:       Main sub-routine
##################################################################
def main():
    # read configuration file
    # if it does not exist set default
    ocOld = ownCloud()
    ocOld.getOCVersion()
    ocOld.getOCConfig()
    # Get command line arguments
    args=getArgs()
    if args.code:
        ocOld.upgradeCodeFileName=args.code
        ocOld.backupOC()
        question="Do you want to install " +ocOld.upgradeFileName+ "?"
        if askYesorNo(question,"yes") is "yes":
            ocOld.installUpgrade()
    if args.check:
        ocOld.checkUpdate()
    if args.backup:
        ocOld.backupOC()
    if args.install:
        # check if an update is available
        # if there is one
        # ask whether to install it
        # backup code and database
        # install upgrade
        ocOld.checkUpdate()
        if(ocOld.updateIsAvailable):
            ocOld.backupOC()
            question="Do you want to install " +ocOld.updateVersionString+ "?"
            if askYesorNo(question,"yes") is "yes":
                ocOld.installUpgrade()
        else:
            print "You are on a current stable release.  No update is available."
main()
