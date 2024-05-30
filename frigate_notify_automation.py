import time
from datetime import timedelta, datetime

event_states = {}

@mqtt_trigger('frigate/events', 'payload_obj["type"] == "new"')
def frigate_new_event(payload_obj=None):
  log.debug(f"Frigate NEW event fired {payload_obj}")
  frigate_id = payload_obj['after']['id']

  event_states[frigate_id] = {
    'images_sent': 0,
  }


@mqtt_trigger('frigate/events', 'payload_obj["type"] == "update"')
def frigate_update_event(payload_obj=None):
  log.debug(f"Frigate UPDATE event fired {payload_obj}")
  frigate_id = payload_obj['after']['id']

  if frigate_id not in event_states:
    log.warning(f"Frigate out of order update for id {frigate_id}")
    return

  if payload_obj['after']['camera'] == 'frigate_driveway' and 'driveway' not in payload_obj['after']['entered_zones']:
    return

  if payload_obj['after']['has_snapshot']:
    log.debug(f"Frigate send snapshot update for {frigate_id}")
    send_image(payload_obj)


@mqtt_trigger('frigate/events', 'payload_obj["type"] == "end"')
def frigate_end_event(payload_obj=None):
  log.debug(f"Frigate END event fired {payload_obj}")
  frigate_id = payload_obj['after']['id']

  if payload_obj['after']['has_clip']:
    send_time = datetime.fromtimestamp(payload_obj['after']['start_time']) + timedelta(seconds=13)
    now = datetime.now()
    if now < send_time:
      remaining_wait = send_time - now
      task.sleep(min(remaining_wait.seconds, 13)) # Likely don't need min just a safety backup

    log.debug(f"Frigate send clip update for {frigate_id}")
    send_clip(payload_obj)

  del event_states[frigate_id]
  if len(event_states) > 0:
    log.warning(f"Frigate {len(event_states)} events pending. This should be 0.")



def send_image(payload_obj):
  frigate_id = payload_obj['after']['id']

  arguments = {
    'title': make_title(payload_obj),
    'message': '',
    'data': {
      'tag': frigate_id,
      'image': make_url(frigate_id, 'snapshot.jpg?bbox=1&crop=1'),
    }
  }

  if event_states[frigate_id]['images_sent'] > 0:
    arguments['data']['channel'] = 'camera_update'
    arguments['data']['importance'] = 'low'

  service.call('notify', 'all_phones', blocking=True, **arguments)
  event_states[frigate_id]['images_sent'] += 1

def send_clip(payload_obj):
  frigate_id = payload_obj['after']['id']
  image_url = make_url(frigate_id, 'snapshot.jpg?bbox=1&crop=1')
  video_url = make_url(frigate_id, 'clip.mp4')

  arguments = {
    'title': make_title(payload_obj),
    'message': '',
    'data': {
      'tag': frigate_id,
      'image': image_url,
      'video':  video_url,
      'channel': 'camera_update',
      'importance': 'low',
      'actions': [
        {
          'action': 'URI',
          'title': 'View Clip',
          'uri': video_url,
        },
        {
          'action': 'URI',
          'title': 'View Snapshot',
          'uri': image_url,
        },
      ]
    }
  }

  service.call('notify', 'all_phones', blocking=True, **arguments)

def make_title(payload_obj):
  camera = payload_obj['after']['camera'][8:].capitalize()
  label = payload_obj['after']['label'].capitalize()
  return f'{camera} - {label} at {time.strftime("%H:%M")}'

def make_url(frigate_id, file_name):
  return f'{hass.config.external_url}/api/frigate/notifications/{frigate_id}/{file_name}'