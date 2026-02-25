(function () {
    'use strict';

    angular.module('theHiveServices').factory('NvApiSrv', function ($http, $q, NvConfig, NotificationSrv, AuthenticationSrv, UtilsSrv) {
        var service = {};
        var baseUrl = NvConfig.nvBaseUrl;

        // Helper to handle errors uniformly
        function handleError(err, context) {
            if (err.status === 403) {
                NotificationSrv.error('Permission Denied', 'You do not have permission to view ' + context);
                return $q.reject(err);
            }
            if (err.status === 404) {
                return $q.reject(err);
            }

            // For other errors (500, timeout), show warning but don't spam notifications if it's just connectivity
            console.warn('NeuralVyuha API Error [' + context + ']:', err);
            // NotificationSrv.error('Service Unavailable', 'NeuralVyuha services are currently unreachable.');
            // Suppress global error to allow fallback logic to proceed silently if needed
            return $q.reject(err);
        }

        function getHeaders() {
            var headers = {};
            if (AuthenticationSrv.currentUser && AuthenticationSrv.currentUser.token) {
                headers.Authorization = 'Bearer ' + AuthenticationSrv.currentUser.token;
            }
            return headers;
        }

        // --- Groups (Incidents) ---
        service.getGroups = function (params) {
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

        // --- Cases (Read-Path Migration) ---
        service.getCases = function(params) {
            return $http.get(baseUrl + '/cases', {
                params: params,
                headers: getHeaders(),
                timeout: NvConfig.timeoutMs
            }).then(function(res) {
                return res.data;
            }).catch(function(err) {
                return handleError(err, 'Case List');
            });
        };

        service.getCase = function(id) {
            return $http.get(baseUrl + '/cases/' + id, {
                headers: getHeaders(),
                timeout: NvConfig.timeoutMs
            }).then(function(res) {
                var data = res.data;
                // Mark as NV source for UI badges
                if (data) {
                    data._source = 'NV';
                }
                return data;
            }).catch(function(err) {
                return handleError(err, 'Case Detail');
            });
        };

        service.getCaseTimeline = function(id) {
             return $http.get(baseUrl + '/cases/' + id + '/timeline', {
                headers: getHeaders(),
                timeout: NvConfig.timeoutMs
            }).then(function(res) {
                return res.data;
            }).catch(function(err) {
                return handleError(err, 'Case Timeline');
            });
        };

        return service;
    });
})();

        // --- Write Operations (Phase E6.4) ---
        service.createCase = function(caze) {
            var headers = getHeaders();
            headers['Idempotency-Key'] = UtilsSrv.uuid(); // Assuming UtilsSrv exists or I need to implement UUID helper

            return $http.post(baseUrl + '/cases', caze, {
                headers: headers,
                timeout: NvConfig.timeoutMs
            }).then(function(res) {
                return res.data;
            }).catch(function(err) {
                return handleError(err, 'Create Case');
            });
        };

        service.updateCase = function(id, updates) {
            var headers = getHeaders();
            // Idempotency key for update? Maybe optional but good practice.
            headers['Idempotency-Key'] = UtilsSrv.uuid();

            return $http.patch(baseUrl + '/cases/' + id, updates, {
                headers: headers,
                timeout: NvConfig.timeoutMs
            }).then(function(res) {
                return res.data;
            }).catch(function(err) {
                return handleError(err, 'Update Case');
            });
        };

        service.createTask = function(caseId, task) {
            var headers = getHeaders();
            headers['Idempotency-Key'] = UtilsSrv.uuid();

            return $http.post(baseUrl + '/cases/' + caseId + '/tasks', task, {
                headers: headers,
                timeout: NvConfig.timeoutMs
            }).then(function(res) {
                return res.data;
            }).catch(function(err) {
                return handleError(err, 'Create Task');
            });
        };

        service.createTaskLog = function(taskId, log) {
             var headers = getHeaders();
            headers['Idempotency-Key'] = UtilsSrv.uuid();

            return $http.post(baseUrl + '/tasks/' + taskId + '/logs', log, {
                headers: headers,
                timeout: NvConfig.timeoutMs
            }).then(function(res) {
                return res.data;
            }).catch(function(err) {
                return handleError(err, 'Create Task Log');
            });
        };
