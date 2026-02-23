'use strict';

describe('Service: V5Router', function () {

  // load the service's module
  beforeEach(module('thehive'));

  var V5Router, V5Config, $httpBackend, $q, NotificationSrv;

  beforeEach(inject(function (_V5Router_, _V5Config_, _$httpBackend_, _$q_, _NotificationSrv_) {
    V5Router = _V5Router_;
    V5Config = _V5Config_;
    $httpBackend = _$httpBackend_;
    $q = _$q_;
    NotificationSrv = _NotificationSrv_;
  }));

  afterEach(function () {
    $httpBackend.verifyNoOutstandingExpectation();
    $httpBackend.verifyNoOutstandingRequest();
  });

  it('should use v4 endpoint when flag is disabled', function () {
    V5Config.useV5QueryReads = false;
    $httpBackend.expectGET('/api/alert?limit=10').respond(200, []);

    V5Router.getAlerts({limit: 10});
    $httpBackend.flush();
  });

  it('should use v5 endpoint when flag is enabled', function () {
    V5Config.useV5QueryReads = true;
    $httpBackend.expectGET('/api/v5/alerts?limit=10').respond(200, []);

    V5Router.getAlerts({limit: 10});
    $httpBackend.flush();
  });

  it('should fallback to v4 on v5 timeout', function () {
    V5Config.useV5QueryReads = true;
    V5Config.fallbackToV4 = true;

    // v5 fails
    $httpBackend.expectGET('/api/v5/alerts?limit=10').respond(504, 'Gateway Timeout');
    // fallback v4
    $httpBackend.expectGET('/api/alert?limit=10').respond(200, []);

    V5Router.getAlerts({limit: 10});
    $httpBackend.flush();
  });

  it('should NOT fallback on 403 Forbidden', function () {
    V5Config.useV5QueryReads = true;
    V5Config.fallbackToV4 = true;
    spyOn(NotificationSrv, 'error');

    $httpBackend.expectGET('/api/v5/alerts?limit=10').respond(403, 'Forbidden');

    V5Router.getAlerts({limit: 10}).catch(function(err) {
      expect(err.status).toBe(403);
    });

    $httpBackend.flush();
    expect(NotificationSrv.error).toHaveBeenCalled();
  });

});
