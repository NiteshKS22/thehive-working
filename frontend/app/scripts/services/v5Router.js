'use strict';

angular.module('thehive').factory('V5Router', function($http, $q, V5Config, NotificationSrv) {

  var service = {};

  // Helper to handle fallback
  function tryV5OrElse(v5Promise, v4FallbackFn) {
    if (!V5Config.useV5QueryReads) {
      return v4FallbackFn();
    }

    return v5Promise.catch(function(err) {
      // 403 Forbidden -> Show Error (Do not fallback)
      if (err.status === 403) {
        NotificationSrv.error('Permission Denied', 'You do not have permission to view this resource in v5.');
        return $q.reject(err);
      }

      // 401 Unauthorized -> Let interceptor handle login
      if (err.status === 401) {
        return $q.reject(err);
      }

      // Other Errors (5xx, Timeout, Network) -> Fallback
      if (V5Config.fallbackToV4) {
        console.warn('v5 Query API failed/timed out. Falling back to v4.', err);
        // Optional: Show banner "Showing legacy data"
        return v4FallbackFn();
      }

      // No fallback configured
      return $q.reject(err);
    });
  }

  // Alerts List
  service.getAlerts = function(params) {
    var v5Request = $http.get(V5Config.v5BaseUrl + '/alerts', {
      params: params,
      timeout: V5Config.timeoutMs
    });

    // Fallback: Legacy v4 endpoint
    var v4Request = function() {
      return $http.get('/api/alert', { params: params });
    };

    return tryV5OrElse(v5Request, v4Request);
  };

  // Alert Details
  service.getAlert = function(id) {
    var v5Request = $http.get(V5Config.v5BaseUrl + '/alerts/' + id, {
      timeout: V5Config.timeoutMs
    });

    var v4Request = function() {
      return $http.get('/api/alert/' + id);
    };

    return tryV5OrElse(v5Request, v4Request);
  };

  return service;
});
