(function () {
    'use strict';

    angular.module('theHiveServices').factory('NvApiSrv', function ($http, $q, NvConfig, NotificationSrv, AuthenticationSrv) {
        var service = {};
        var baseUrl = NvConfig.nvBaseUrl;

        // Helper to handle errors uniformly
        function handleError(err, context) {
            if (err.status === 403) {
                NotificationSrv.error('Permission Denied', 'You do not have permission to view ' + context);
                // Fail Open: Return empty/safe result so UI doesn't crash, or reject?
                // Requirement: "Show a clean 'Service Unavailable' state, don't crash the v4 UI shell."
                // Rejecting allows the controller to handle loading state.
                return $q.reject(err);
            }
            if (err.status === 404) {
                return $q.reject(err);
            }

            // For other errors (500, timeout), show warning but don't spam notifications if it's just connectivity
            console.warn('NeuralVyuha API Error [' + context + ']:', err);
            NotificationSrv.error('Service Unavailable', 'NeuralVyuha services are currently unreachable.');
            return $q.reject(err);
        }

        function getHeaders() {
            var headers = {};
            // Attempt to attach JWT if available in current user context
            if (AuthenticationSrv.currentUser && AuthenticationSrv.currentUser.token) {
                headers.Authorization = 'Bearer ' + AuthenticationSrv.currentUser.token;
            }
            return headers;
        }

        service.getGroups = function (params) {
            // params: status, severity, limit, offset
            return $http.get(baseUrl + '/groups', {
                params: params,
                headers: getHeaders(),
                timeout: NvConfig.timeoutMs
            }).then(function (res) {
                return res.data;
            }).catch(function (err) {
                return handleError(err, 'Incidents List');
            });
        };

        service.getGroup = function (id) {
            return $http.get(baseUrl + '/groups/' + id, {
                headers: getHeaders(),
                timeout: NvConfig.timeoutMs
            }).then(function (res) {
                return res.data;
            }).catch(function (err) {
                return handleError(err, 'Incident Detail');
            });
        };

        service.getGroupAlerts = function (id) {
            return $http.get(baseUrl + '/groups/' + id + '/alerts', {
                headers: getHeaders(),
                timeout: NvConfig.timeoutMs
            }).then(function (res) {
                return res.data;
            }).catch(function (err) {
                return handleError(err, 'Incident Timeline');
            });
        };

        return service;
    });
})();
