import json
from channels import Group
from .models import Liveblog

from datetime import datetime
from twisted.internet.task import LoopingCall

def update_time(message):
    print("Adding update_time group...", message.reply_channel)
    Group('update_time').add(message.reply_channel)
    maybe_start_looper()

looper = None
def maybe_start_looper():
    global looper
    if not looper:
        looper = LoopingCall(send_message_update_time)
        looper.start(1)
        print("LoopingCall started...")

def send_message_update_time():
    # print("send_message_update_time")
    """
    Sends a notification to everyone in our update_time group with
    the current datetime.
    """
    # Make the payload of the notification. We'll JSONify this, so it has
    # to be simple types, which is why we handle the datetime here.
    notification = {
        "time": str(datetime.now())
    }
    print(notification)
    # Encode and send that message to the whole channels Group for our
    # time server. Note how you can send to a channel or Group from any part
    # of Django, not just inside a consumer.
    # WebSocket text frame, with JSON content
    # Group('update_time').send({'pkt':pkt})
    Group('update_time').send({
        # WebSockets send either a text or binary payload each frame.
        # We do JSON over the text portion.
        "text": json.dumps(notification),
    })
    # {
    #     "time_text": json.dumps(notification)
    # })


# The "slug" keyword argument here comes from the regex capture group in
# routing.py.
def connect_blog(message, slug):
    """
    When the user opens a WebSocket to a liveblog stream, adds them to the
    group for that stream so they receive new post notifications.

    The notifications are actually sent in the Post model on save.
    """
    # Try to fetch the liveblog by slug; if that fails, close the socket.
    print("Trying to create channel for:", slug)
    try:
        liveblog = Liveblog.objects.get(slug=slug)
    except Liveblog.DoesNotExist:
        # You can see what messages back to a WebSocket look like in the spec:
        # http://channels.readthedocs.org/en/latest/asgi.html#send-close
        # Here, we send "close" to make Daphne close off the socket, and some
        # error text for the client.
        message.reply_channel.send({
            # WebSockets send either a text or binary payload each frame.
            # We do JSON over the text portion.
            "text": json.dumps({"error": "bad_slug"}),
            "close": True,
        })
        return
    # Each different client has a different "reply_channel", which is how you
    # send information back to them. We can add all the different reply channels
    # to a single Group, and then when we send to the group, they'll all get the
    # same message.
    Group(liveblog.group_name).add(message.reply_channel)


def disconnect_blog(message, slug):
    """
    Removes the user from the liveblog group when they disconnect.

    Channels will auto-cleanup eventually, but it can take a while, and having old
    entries cluttering up your group will reduce performance.
    """
    try:
        liveblog = Liveblog.objects.get(slug=slug)
    except Liveblog.DoesNotExist:
        # This is the disconnect message, so the socket is already gone; we can't
        # send an error back. Instead, we just return from the consumer.
        return
    # It's called .discard() because if the reply channel is already there it
    # won't fail - just like the set() type.
    Group(liveblog.group_name).discard(message.reply_channel)
