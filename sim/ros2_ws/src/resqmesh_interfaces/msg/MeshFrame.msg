# One radio frame on the emulated disaster mesh. Every hop is a separate frame (src -> next hop).
string src                    # transmitting node this hop
string dst                    # next-hop node, or "*" for a broadcast (hello beacons)
string origin                 # node that created the message
string final                  # destination node of the message ("base" for the rescue base)
string kind                   # hello | sighting | status | plan | event | ack ...
uint32 msg_id
uint8 ttl
uint8 hops
string payload                # JSON
