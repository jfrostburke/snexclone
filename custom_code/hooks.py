import os
import requests
import logging
from astropy.time import Time, TimezoneInfo
from tom_dataproducts.models import ReducedDatum
import json
from tom_targets.templatetags.targets_extras import target_extra_field
from requests_oauthlib import OAuth1
from astropy.coordinates import SkyCoord
from astropy import units as u

logger = logging.getLogger(__name__)

def target_post_save(target, created):
  def get(objectId):
    url = 'https://mars.lco.global/'
    request = {'queries':
      [
        {'objectId': objectId}
      ]
      }
  
    try:
      r = requests.post(url, json=request)
      results = r.json()['results'][0]['results']
      return results
    
    except Exception as e:
      return [None,'Error message : \n'+str(e)]
 
  logger.info('Target post save hook: %s created: %s', target, created)

  if target_extra_field(target=target, name='tweet'):
    #Post to Twitter!
    twitter_url = 'https://api.twitter.com/1.1/statuses/update.json'

    api_key = os.environ['TWITTER_APIKEY']
    api_secret = os.environ['TWITTER_SECRET']
    access_token = os.environ['TWITTER_ACCESSTOKEN']
    access_secret = os.environ['TWITTER_ACCESSSECRET']
    auth = OAuth1(api_key, api_secret, access_token, access_secret)

    coords = SkyCoord(target.ra, target.dec, unit=u.deg)
    coords = coords.to_string('hmsdms', sep=':',precision=1,alwayssign=True)

    #Explosion emoji
    tweet = ''.join([u'\U0001F4A5 New target alert! \U0001F4A5\n',
        'Name: {name}\n'.format(name=target.name),
        'Coordinates: {coords}\n'.format(coords=coords)])
    status = {
            'status': tweet
    }

    response = requests.post(twitter_url, params=status, auth=auth)
 

  if 'ZTF' in target.name:
    objectId = target.name 
    alerts = get(objectId)
    
    filters = {1: 'g_ZTF', 2: 'r_ZTF', 3: 'i_ZTF'}
    for alert in alerts:
        if all([key in alert['candidate'] for key in ['jd', 'magpsf', 'fid', 'sigmapsf']]):
            jd = Time(alert['candidate']['jd'], format='jd', scale='utc')
            jd.to_datetime(timezone=TimezoneInfo())
            value = {
                'magnitude': alert['candidate']['magpsf'],
                'filter': filters[alert['candidate']['fid']],
                'error': alert['candidate']['sigmapsf']
            }
            rd, created = ReducedDatum.objects.get_or_create(
                timestamp=jd.to_datetime(timezone=TimezoneInfo()),
                value=json.dumps(value),
                source_name=target.name,
                source_location=alert['lco_id'],
                data_type='photometry',
                target=target)
            rd.save()
