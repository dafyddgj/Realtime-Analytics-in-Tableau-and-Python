# -*- coding: utf-8 -*-

from tweepy import Stream
from tweepy import OAuthHandler
from tweepy import API
from tweepy.streaming import StreamListener
import csv
import json
import os
# download from https://onlinehelp.tableau.com/current/api/sdk/en-us/help.htm#SDK/tableau_sdk_installing.htm
import tableausdk.Extract as data
import tableausdk.Types as types
import re
import sys
from datetime import datetime
from textblob import TextBlob
import time

# put your keys here. Get them by registering an app on dev.twitter.com
keys = {
    'screen_name':'begahtan',
    'consumer_key': 'JCIxDA6kzvUa0KGdJqmXVjdMH',
    'consumer_secret': 'raC1O9p93O6HgchX5XHAi7LtLiYHZLNJ2WcvRRc8bA3zU19Vbq',
    'access_token': '730632422786777089-EqzoJ6wV3mVVmfQJTdu4dRHkj632vcd',
    'access_token_secret': '566GgwcjCx5pHAOyboQL9G8yIHe6MzPUjmPTHcRBvFa6p'
}

SCREEN_NAME = keys['screen_name']
CONSUMER_KEY = keys['consumer_key']
CONSUMER_SECRET = keys['consumer_secret']
ACCESS_TOKEN = keys['access_token']
ACCESS_TOKEN_SECRET = keys['access_token_secret']

# this is the term we will search for on twitter
TRACK_TERM = "#SundayFunday"

# some ugly global variables
tweet_count = 0
file_number = 0
current_file = None

WORKING_DIRECTORY = os.getcwd()

def record_tweet(status, file_number):
    # this function unpacks a tweet in JSON form and writes it to a CSV file.
    # it also calculates the sentiment of the text of the tweet.

    tweet = json.loads(status)

    if 'limit' in tweet:
        print "hit limit:", tweet

    data_to_write = {}

    try:
        data_to_write["tweet_text"] = tweet['text']

        # source comes as a long string: "<a href=""http://twitter.com"" rel=""nofollow"">Twitter Web Client</a>
        data_to_write["source"] = re.findall(r">(.*)<", tweet['source'])[0]

        data_to_write["user"] = tweet['user']['screen_name']
        data_to_write["lang"] = tweet['lang']
        data_to_write["created_at"] = tweet['created_at']

        if tweet['geo'] != None:
            lat, lon = str(tweet['geo']['coordinates'])[1:-1].split(', ')
            data_to_write["latitude"] = lat
            data_to_write["longitude"] = lon
        else:
            data_to_write["latitude"] = ""
            data_to_write["longitude"] = ""

        if tweet['place'] != None:
            data_to_write["country"] = tweet['place']['country']
        else:
            data_to_write["country"] = ""

        # get the sentiment of the tweet using TextBlob (-1 is very bad, 1 is very positive)
        tweet = TextBlob(tweet['text'])
        data_to_write['sentiment'] = tweet.sentiment.polarity

    except Exception as e:
        print "error:", e
        pass

    # super lazy way to encode the strings as utf-8
    for key in data_to_write.keys():
        if data_to_write[key] == None:
            data_to_write[key] = ""
        try:
            data_to_write[key] = data_to_write[key].encode('utf-8')
        except Exception as e:
            # print "error:", e
            pass

    # figure out what CSV file to write the tweet to
    global current_file, TRACK_TERM
    file_name = TRACK_TERM + '_' + str(file_number) + '.csv'

    if current_file != file_name:
        print "creating", file_name
        with open(file_name, 'wb') as outf:
            writer = csv.DictWriter(outf, delimiter=',', lineterminator='\n', fieldnames=data_to_write.keys())
            writer.writeheader()
            writer.writerow(data_to_write)
        current_file = TRACK_TERM + '_' + str(file_number) + '.csv'

    else:
        with open(file_name, 'a') as outf:
            writer = csv.DictWriter(outf, delimiter=',', lineterminator='\n', fieldnames=data_to_write.keys())
            writer.writerow(data_to_write)

    return

def extract(file_name):
    # move file to /extract
    # cd to /extract
    # if there is no extract called TRACK_TERM then create one, otherwise append to TRACK_TERM
    # define data model for extract

    global WORKING_DIRECTORY, TRACK_TERM

    if not os.path.exists(WORKING_DIRECTORY + '/extract/'):
        os.makedirs(WORKING_DIRECTORY + '/extract/')

    from_path = WORKING_DIRECTORY + '/' + file_name
    to_path = WORKING_DIRECTORY + '/extract/' + file_name

    os.rename(from_path, to_path)

    os.chdir(WORKING_DIRECTORY + '/extract')

    # define the extract
    with data.Extract(TRACK_TERM + '.tde') as extract:

        tableDef = data.TableDefinition()

        # define the columns and the data types in the extract
        tableDef.addColumn('lang',          types.Type.CHAR_STRING) #0
        tableDef.addColumn('sentiment',     types.Type.DOUBLE)      #1
        tableDef.addColumn('country',       types.Type.CHAR_STRING) #2
        tableDef.addColumn('created_at',    types.Type.DATETIME)    #3
        tableDef.addColumn('tweet_text',    types.Type.CHAR_STRING) #4
        tableDef.addColumn('Longitude',     types.Type.DOUBLE)      #5
        tableDef.addColumn('source',        types.Type.CHAR_STRING) #6
        tableDef.addColumn('user',          types.Type.CHAR_STRING) #7
        tableDef.addColumn('Latitude',      types.Type.DOUBLE)      #8

        table = None

        if not extract.hasTable('Extract'):
            # Table does not exist, so create it.
            print "Creating a new extract"
            table = extract.addTable('Extract', tableDef)
        else:
            # Table exists, so append the new data.
            print "Appending to an existing extract"
            table = extract.openTable('Extract')

        new_row = data.Row(tableDef)

        # read the data from the CSV into the extract row object
        with open(file_name, 'r') as inf:
            reader = csv.DictReader(inf, delimiter=',', lineterminator='\n')
            for row in reader:
                # insert data into the row object in the correct order as defined above
                new_row.setCharString(0, row['lang'])

                sentiment = float(row['sentiment'])
                new_row.setDouble(1, sentiment)

                new_row.setCharString(2, row['country'])

                # parse the twitter date string:
                # Mon Sep 21 11:03:53 +0000 2015
                # %a %b %d %H:%M:%S +0000 %Y
                date_object = datetime.strptime(row['created_at'], '%a %b %d %H:%M:%S +0000 %Y')
                year = int(datetime.strftime(date_object,'%Y'))
                month = int(datetime.strftime(date_object,'%m'))
                day = int(datetime.strftime(date_object,'%d'))
                hour = int(datetime.strftime(date_object,'%H'))
                min = int(datetime.strftime(date_object,'%M'))
                sec = int(datetime.strftime(date_object,'%S'))
                frac = 0 # fractions of a second aka milliseconds
                new_row.setDateTime(3, year, month, day, hour, min, sec, frac)

                new_row.setCharString(4, row['tweet_text'])

                # check if there is a value for longitude, otherwise write a 0
                try:
                    longitude = float(row['longitude'])
                except:
                    longitude = 0
                new_row.setDouble(5, longitude)

                new_row.setCharString(6, row['source'])
                new_row.setCharString(7, row['user'])

                # check if there is a value for latitude, otherwise write a 0
                try:
                    latitude = float(row['latitude'])
                except:
                    latitude = 0
                new_row.setDouble(8, latitude)

                table.insert(new_row)

    # if the process fails we want to be able to re-run it without collisions between file names
    # so give each file a unique name (unix time stamp in this case).
    os.rename(file_name, str(time.time()).split('.')[0]+'.csv')

    # cd back to working directory
    os.chdir(WORKING_DIRECTORY)

    return

class StdOutListener( StreamListener ):

    def __init__( self ):
        self.tweetCount = 0

    def on_connect( self ):
        print("Connection established!")

    def on_disconnect( self, notice ):
        print("Connection lost! : ", notice)

    def on_data( self, status ):
        # when a tweet is found that matches the search term:

        global tweet_count, file_number
        tweet_count += 1

        if tweet_count % 10 == 0:
            print ".",

        # after we capture 50 tweets go ahead and write them to the extract
        if tweet_count % 20 == 0:
            print "\rcaptured %s tweets in file #%s" % (20, str(file_number))
            file_number += 1
            extract(current_file)

        # record each tweet in a CSV file
        record_tweet(status, file_number)

        return True

    def on_error( self, status ):
        print status

if __name__ == '__main__':

    try:
        auth = OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
        auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
        auth.secure = True
        api = API(auth)

        print(api.me().name)

        stream = Stream(auth, StdOutListener())
        stream.filter(track=[TRACK_TERM])

    except Exception as e:
        print "error:", e
        pass