(function () {
    'use strict';

    angular.module('theHiveServices').factory('NvApiSrv', function (, , NvConfig, NotificationSrv, AuthenticationSrv, UtilsSrv) {
        var service = {};
        var baseUrl = NvConfig.nvBaseUrl;

        // Helper to handle errors uniformly
        function handleError(err, context) {
            if (err.status === 403) {
                NotificationSrv.error('Permission Denied', 'You do not have permission to view ' + context);
                return .reject(err);
            }
            if (err.status === 404) {
                return .reject(err);
            }

            console.warn('NeuralVyuha API Error [' + context + ']:', err);
            return .reject(err);
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
            return .get(baseUrl + '/groups', {
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
            return .get(baseUrl + '/groups/' + id, {
                headers: getHeaders(),
                timeout: NvConfig.timeoutMs
            }).then(function (res) {
                return res.data;
            }).catch(function (err) {
                return handleError(err, 'Incident Detail');
            });
        };

        service.getGroupAlerts = function (id) {
            return .get(baseUrl + '/groups/' + id + '/alerts', {
                headers: getHeaders(),
                timeout: NvConfig.timeoutMs
            }).then(function (res) {
                return res.data;
            }).catch(function (err) {
                return handleError(err, 'Incident Timeline');
            });
        };

        // --- Cases ---
        service.getCases = function(params) {
            return .get(baseUrl + '/cases', {
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
            return .get(baseUrl + '/cases/' + id, {
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
             return .get(baseUrl + '/cases/' + id + '/timeline', {
                headers: getHeaders(),
                timeout: NvConfig.timeoutMs
            }).then(function(res) {
                return res.data;
            }).catch(function(err) {
                return handleError(err, 'Case Timeline');
            });
        };

        // --- Write Operations ---
        service.createCase = function(caze) {
            var headers = getHeaders();
            headers['Idempotency-Key'] = UtilsSrv.uuid();

            return .post(baseUrl + '/cases', caze, {
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
            headers['Idempotency-Key'] = UtilsSrv.uuid();

            return .patch(baseUrl + '/cases/' + id, updates, {
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

            return .post(baseUrl + '/cases/' + caseId + '/tasks', task, {
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

            return .post(baseUrl + '/tasks/' + taskId + '/logs', log, {
                headers: headers,
                timeout: NvConfig.timeoutMs
            }).then(function(res) {
                return res.data;
            }).catch(function(err) {
                return handleError(err, 'Create Task Log');
            });
        };

        return service;
    });
})();
