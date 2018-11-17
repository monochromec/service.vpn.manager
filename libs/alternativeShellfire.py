#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#    Copyright (C) 2018 Zomboided
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
#
#    Code fragments specific to individual VPN providers.

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
import json
import urllib2
import time
from libs.utility import ifHTTPTrace, ifJSONTrace, debugTrace, infoTrace, errorTrace, ifDebug, newPrint, getID, now
from libs.platform import getAddonPath
from libs.access import setVPNRequestedServer, getVPNRequestedServer, resetTokens, setTokens, getTokens


REQUEST_HEADERS = {
    "x-shellfirevpn-client-os": "kodi",
    "x-shellfirevpn-client-arch": "zomboided",
    "x-shellfirevpn-client-version": "0.1"
}

REQUEST_URL = "https://www.shellfire.de/webservice/json.php"

SHELLFIRE_LOCATIONS = "COUNTRIES.txt"

TIME_WARN = 10


def authenticateLogin(vpn_provider, userid, password):
    # Authenticate to get token
    try: 
        response = ""
        api_data = ""
        rest_url = REQUEST_URL + "?action=login"
        rest_data = '{"email":"' + userid + '", "password":"' + password + '"}'

        if ifHTTPTrace(): infoTrace("alternativeShellfire.py", "Authenticating with VPN using " + rest_url + ", " + rest_data)     
        else: debugTrace("Authenticating with VPN for user " + userid)

        req = urllib2.Request(rest_url, rest_data, REQUEST_HEADERS)
        t_before = now()
        response = urllib2.urlopen(req)
        api_data = json.load(response)
        t_after = now()
        response.close()

        if ifJSONTrace(): infoTrace("alternativeShellfire.py", "JSON received is \n" + json.dumps(api_data, indent=4))
        if t_after - t_before > TIME_WARN: infoTrace("alternativeShellfire.py", "Authenticating with VPN for " + userid + " took " + str(t_after - t_before) + " seconds")

        if not api_data["status"] == "success":
            raise Exception("Bad response authenticating with VPN, " + api_data["status"] + " check user ID and password")
        
        # Return the token to use for this user on future API calls
        return api_data["data"]["token"]

    except urllib2.HTTPError as e:
        errorTrace("alternativeShellfire.py", "Couldn't authenticate with " + vpn_provider)
        errorTrace("alternativeShellfire.py", "API call was " + rest_url + ", " + rest_data[:rest_data.index("password")+10] + "********}")
        if not api_data == "": errorTrace("alternativeShellfire.py", "Data returned was \n" + json.dumps(api_data, indent=4))
        errorTrace("alternativeShellfire.py", "Response was " + str(e.code) + " " + e.reason)
        errorTrace("alternativeShellfire.py", e.read())
    except Exception as e:
        errorTrace("alternativeShellfire.py", "Couldn't authenticate with " + vpn_provider)
        errorTrace("alternativeShellfire.py", "API call was " + rest_url + ", " + rest_data[:rest_data.index("password")+10] + "********}")
        if not api_data == "": errorTrace("alternativeShellfire.py", "Data returned was \n" + json.dumps(api_data, indent=4))
        errorTrace("alternativeShellfire.py", "Response was " + str(type(e)) + " " + str(e))

    return None
    
    
def authenticateGetServices(auth_token):
    # Get the list of services  
    try:
        response = ""
        api_data = ""
        rest_url = REQUEST_URL + "?action=getAllVpnDetails"
        
        if ifHTTPTrace(): infoTrace("alternativeShellfire.py", "Retrieving list of services " + rest_url)     
        else: debugTrace("Retrieving list of services")
        
        req = urllib2.Request(rest_url, "", REQUEST_HEADERS)
        req.add_header("x-authorization-token", auth_token)
        t_before = now()
        response = urllib2.urlopen(req)
        api_data = json.load(response)   
        t_after = now()    
        response.close()

        if ifJSONTrace(): infoTrace("alternativeShellfire.py", "JSON received is \n" + json.dumps(api_data, indent=4))
        if t_after - t_before > TIME_WARN: infoTrace("alternativeShellfire.py", "Retrieving list of services took " + str(t_after - t_before) + " seconds")
        
        if not api_data["status"] == "success":
            raise Exception("Bad response getting services from VPN provider, " + api_data["status"])
        
        # Extract and return the list of service levels the user is entitled to
        services = ""
        for item in api_data["data"]:
            services = services + item["eAccountType"] + " "
        debugTrace("User has " + services + "active")
        
        return services    
    
    except urllib2.HTTPError as e:
        errorTrace("alternativeShellfire.py", "Couldn't retrieve the list of services")
        errorTrace("alternativeShellfire.py", "API call was " + rest_url)
        if not api_data == "": errorTrace("alternativeShellfire.py", "Data returned was \n" + json.dumps(api_data, indent=4))
        errorTrace("alternativeShellfire.py", "Response was " + str(e.code) + " " + e.reason)
        errorTrace("alternativeShellfire.py", e.read())
    except Exception as e:
        errorTrace("alternativeShellfire.py", "Couldn't retrieve the list of services")
        errorTrace("alternativeShellfire.py", "API call was " + rest_url)
        if not api_data == "": errorTrace("alternativeShellfire.py", "Data returned was \n" + json.dumps(api_data, indent=4))
        errorTrace("alternativeShellfire.py", "Response was " + str(type(e)) + " " + str(e))
    
    return None


def authenticateShellfire(vpn_provider, userid, password):
    # Authenticate with the API and store the tokens returned

    # If the same credentials have been used before, don't bother authenticating
    _,_,_, creds = getTokens()
    # FIXME REMOVE THIS AFTER TESTING
    if 1==0 and creds == vpn_provider + userid + password: 
        debugTrace("Previous authentication was good")
        return True
    
    # Get the authentication token to use on future calls
    auth_token = authenticateLogin(vpn_provider, userid, password)
    if not auth_token == None: 
        services = authenticateGetServices(auth_token)
        if not services == None:
            # Store all of the authentication info
            setTokens(auth_token, services, vpn_provider + userid + password)
            return True

    # Authentication or retrieval of services failed so clean up
    resetTokens()
    return False


def getShellfirePreFetch(vpn_provider):
    # Fetch and store country info
    filename = getAddonPath(True, vpn_provider + "/" + SHELLFIRE_LOCATIONS)
    if xbmcvfs.exists(filename):
        try:
            st = xbmcvfs.Stat(filename)
            create_time = int(st.st_ctime())
            t = now()
            # Fetch again if this is more than a day old otherwise use what there is
            if create_time + 86400 < t:
                debugTrace("Create time of " + filename + " is " + str(create_time) + " time now is " + str(t) + ", fetching country data again")
            else:
                debugTrace("Create time of " + filename + " is " + str(create_time) + " time now is " + str(t) + ", using existing data")
                # <FIXME> Remove this after testing, this forces the list to always be downloaded
                # return True
        except Exception as e:
            errorTrace("alternativeShellfire.py", "List of countries exist but couldn't get the time stamp for " + filename)
            errorTrace("alternativeShellfire.py", str(e))
            return False

    # Download the list of countries
    error = True
    try:
        response = ""
        api_data = ""
        rest_url = "https://www.shellfire.de/webservice/serverlist.php"
        
        if ifHTTPTrace(): infoTrace("alternativeShellfire.py", "Downloading list of countries using " + rest_url)
        else: debugTrace("Downloading list of countries")
        
        # This is not a JSON call, a header and servers are returned in a ; separated list
        req = urllib2.Request(rest_url, "", REQUEST_HEADERS)
        t_before = now()
        response = urllib2.urlopen(req)
        api_data = response.read()
        t_after = now()    
        response.close()

        if ifJSONTrace(): infoTrace("alternativeShellfire.py", "Text received is \n" + api_data)
        if t_after - t_before > TIME_WARN: infoTrace("alternativeShellfire.py", "Retrieving list of countries took " + str(t_after - t_before) + " seconds")
        
    except urllib2.HTTPError as e:
        errorTrace("alternativeShellfire.py", "Couldn't retrieve the list of countries")
        errorTrace("alternativeShellfire.py", "API call was " + rest_url)
        if not api_data == "": errorTrace("alternativeShellfire.py", "Data returned was \n" + api_data)
        errorTrace("alternativeShellfire.py", "Response was " + str(e.code) + " " + e.reason)
        errorTrace("alternativeShellfire.py", e.read())
    except Exception as e:
        errorTrace("alternativeShellfire.py", "Couldn't retrieve the list of countries")
        errorTrace("alternativeShellfire.py", "API call was " + rest_url)
        if not api_data == "": errorTrace("alternativeShellfire.py", "Data returned was \n" + api_data)
        errorTrace("alternativeShellfire.py", "Response was " + str(type(e)) + " " + str(e))
            
    # The first line has the headers, so find the position of the information that's interesting
    api_table = api_data.split("\n") 
    headers = api_table[0].split(";")
    country_pos = headers.index("Country")
    city_pos = headers.index("sCity")
    host_pos = headers.index("sHost")
    type_pos = headers.index("eServerType")    
    debugTrace("Header decoded.  Country is " + str(country_pos) + ", City is " + str(city_pos) + ", Host is " + str(host_pos) + ", Type is " + str(type_pos))    

    try:
        line = ""
        debugTrace("Parsing the text and writing the list of countries")
        output = open(filename, 'w')
        # Parse the data and create a file containing the stuff we care about
        i = 0
        for line in api_table:       
            if i > 0:
                server_data = line.split(";")
                # Avoid parsing empty lines, or lines where there's not enough data and output the result
                if len(server_data) > 4:
                    output.write(server_data[country_pos] + " - " + server_data[city_pos] + "," + server_data[host_pos] + "," + server_data[type_pos] + "\n")
            i += 1
        output.close()
        return True
    except Exception as e:
        errorTrace("alternativeShellfire`.py", "Couldn't write the list of countries for " + vpn_provider + " to " + filename)
        if not server_data == "": errorTrace("alternativeShellfire.py", "Processing server " + line)
        errorTrace("alternativeShellfire.py", str(e))
    
    # Delete the country file if the was a problem creating it.  This will force a download next time through
    try:
        if xbmcvfs.exists(filename): 
            errorTrace("alternativeShellfire.py", "Deleting country file " + filename + " to clean up after previous error")
            xbmcvfs.delete(filename)
    except Exception as e:
        errorTrace("alternativeShellfire.py", "Couldn't delete the country file " + filename)
        errorTrace("alternativeShellfire.py", str(e))
    return False
        
    
def getShellfireLocationsCommon(vpn_provider, exclude_used, friendly):
    getShellfirePreFetch(vpn_provider)
    return []
    

def getShellfireFriendlyLocations(vpn_provider, exclude_used):
    return getShellfireLocationsCommon(vpn_provider, exclude_used, True)


def getShellfireLocations(vpn_provider, exclude_used):
    return getShellfireLocationsCommon(vpn_provider, exclude_used, False)


def getShellfireLocationName(vpn_provider, location):
    # <FIXME> although this is probably right
    return getAddonPath(True, vpn_provider + "/" + location + ".ovpn")
    
    
def getShellfireLocation(vpn_provider, location, server_count):
    # <FIXME>
    return "", ""
    

def getShellfireServers(vpn_provider, exclude_used):
    # Return a list of all of the server files
    # Not supported for this provider
    return []

    
def getShellfireFriendlyServers(vpn_provider, exclude_used):
    # Return a list of all of the servers
    # Not supported for this provider
    return []


def getShellfireServer(vpn_provider, server, server_count):
    # Return friendly name and .ovpn file name
    # Not supported for this provider
    return "", ""
    

def regenerateShellfire(vpn_provider):
    # <FIXME>
    return True


def resetShellfire(vpn_provider):
    # <FIXME>
    return True


def getShellfireUserPass(vpn_provider):
    # Use the user ID and password entered into the GUI
    # <FIXME> This might need reviewing depending on the data that comes back from the call to get the params
    addon = xbmcaddon.Addon(getID())
    return addon.getSetting("vpn_username"), addon.getSetting("vpn_password")
    

