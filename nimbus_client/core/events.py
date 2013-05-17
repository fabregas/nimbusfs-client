#!/usr/bin/python
"""
Copyright (C) 2013 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package nimbus_client.core.events
@author Konstantin Andrusenko
@date May 19, 2013

This module contains the implementation of Event and EventProvider classes
Also exports global events_provider object for easy events sending 
"""
from datetime import datetime

from nimbus_client.core.base_safe_object import LockObject
from nimbus_client.core.logger import logger

ELock = LockObject()

class Event:
    #event types
    ET_INFO = 0
    ET_WARNING = 1
    ET_ERROR = 2
    ET_CRITICAL = 3

    ET_MAP = {ET_INFO: 'INFO',
              ET_WARNING: 'WARNING',
              ET_ERROR: 'ERROR',
              ET_CRITICAL: 'CRITICAL'}

    def __init__(self, event_type, event_provider, message):
        if event_type not in self.ET_MAP:
            raise Exception('Event type "%s" does not expected!'%event_type)

        self.__event_type = event_type
        self.__event_provider = event_provider
        self.__message = message
        self.__datetime = datetime.now()

    def __repr__(self):
        return '[%s][%s]{%s} %s'%(self.ET_MAP.get(self.__event_type), \
                self.__datetime.strftime("%d-%m-%y %H:%M:%S"),\
                self.__event_provider, self.__message)

    def get_event_type(self):
        return self.__event_type

    def get_event_provider(self):
        return self.__event_provider

    def get_message(self):
        return self.__message

    def get_datetime(self):
        return self.__datetime



class EventsProvider:
    def __init__(self):
        self.__listeners = {}
        self.__sorted_et_list = Event.ET_MAP.keys()
        self.__sorted_et_list.sort()
        for et in self.__sorted_et_list:
            self.__listeners[et] = []

    @ELock
    def append_listener(self, event_type, listener):
        """appends listener routine to events processor
        Listener function should have signature:
            listener(event)
        When event with type >= event_type will emit, 
        this listner function should be called"""
        if event_type not in Event.ET_MAP:
            raise Exception('Event type "%s" does not expected!'%event_type)
        self.__listeners[event_type].append(listener)

    @ELock
    def emit(self, event_type, event_provider, message):
        event = Event(event_type, event_provider, message)

        si = self.__sorted_et_list.index(event_type)
        for et in self.__sorted_et_list[:si+1]:
            for listener in self.__listeners[et]:
                listener(event)

    def info(self, event_provider, message):
        logger.info(message)
        self.emit(Event.ET_INFO, event_provider, message)

    def warning(self, event_provider, message):
        logger.warning(message)
        self.emit(Event.ET_WARNING, event_provider, message)

    def error(self, event_provider, message):
        logger.error(message)
        self.emit(Event.ET_ERROR, event_provider, message)

    def critical(self, event_provider, message):
        logger.critical(message)
        self.emit(Event.ET_CRITICAL, event_provider, message)


events_provider = EventsProvider()

