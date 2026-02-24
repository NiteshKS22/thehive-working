'use strict';

angular.module('theHiveServices').factory('V5Router', function($http, $q, V5Config, NotificationSrv) {

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
    }).then(function(res) {
        return res.data; // Adapter expects data
    });

    // Fallback: Legacy v4 endpoint
    // Note: Legacy list() returns PaginatedQuerySrv object, but here we just return the data promise
    // The V5ListAdapter handles the structure.
    // Ideally, fallback should return promise resolving to v4 data.
    var v4Request = function() {
      // Direct call to v4 API mimicking PaginatedQuerySrv internal call
      return $http.post('/api/v1/query', { query: { _name: 'listAlert' }, filter: params.filter, sort: params.sort }).then(function(res) { return res.data; });
    };

    return tryV5OrElse(v5Request, v4Request);
  };

  // Alert Details
  service.getAlert = function(id) {
    var v5Request = $http.get(V5Config.v5BaseUrl + '/alerts/' + id, {
      timeout: V5Config.timeoutMs
    }).then(function(res) {
        return res.data;
    });

    var v4Request = function() {
      return $http.get('./api/v1/alert/' + id).then(function(res) { return res.data; });
    };

    return tryV5OrElse(v5Request, v4Request);
  };

  return service;
});
