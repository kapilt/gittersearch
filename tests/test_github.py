from hubhud.github import get_events


def test_get_custodian_events():

    events = get_events('cloud-custodian/cloud-custodian', direction='desc')
    events = list(events)
    assert len(events) == 100
    assert events[0].event_type

    
