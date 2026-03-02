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

        service.getAlerts = function (params) {
            return $http.get(baseUrl + '/alerts', {
                params: params,
                headers: getHeaders(),
                timeout: NvConfig.timeoutMs
            }).then(function (res) {
                return res.data;
            }).catch(function (err) {
                return handleError(err, 'Alerts List');
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
        service.getCases = function (params) {
            return $http.get(baseUrl + '/cases', {
                params: params,
                headers: getHeaders(),
                timeout: NvConfig.timeoutMs
            }).then(function (res) {
                return res.data;
            }).catch(function (err) {
                return handleError(err, 'Case List');
            });
        };

        service.getCase = function (id) {
            return $http.get(baseUrl + '/cases/' + id, {
                headers: getHeaders(),
                timeout: NvConfig.timeoutMs
            }).then(function (res) {
                var data = res.data;
                // Mark as NV source for UI badges
                if (data) {
                    data._source = 'NV';
                }
                return data;
            }).catch(function (err) {
                return handleError(err, 'Case Detail');
            });
        };

        service.getCaseTimeline = function (id) {
            return $http.get(baseUrl + '/cases/' + id + '/timeline', {
                headers: getHeaders(),
                timeout: NvConfig.timeoutMs
            }).then(function (res) {
                return res.data;
            }).catch(function (err) {
                return handleError(err, 'Case Timeline');
            });
        };

        // --- Write Operations (Phase E6.4) ---
        service.createCase = function (caze) {
            var headers = getHeaders();
            headers['Idempotency-Key'] = UtilsSrv.guid(); // Assuming UtilsSrv exists or I need to implement UUID helper

            return $http.post(baseUrl + '/cases', caze, {
                headers: headers,
                timeout: NvConfig.timeoutMs
            }).then(function (res) {
                return res.data;
            }).catch(function (err) {
                return handleError(err, 'Create Case');
            });
        };

        service.updateCase = function (id, updates) {
            var headers = getHeaders();
            // Idempotency key for update? Maybe optional but good practice.
            headers['Idempotency-Key'] = UtilsSrv.guid();

            return $http.patch(baseUrl + '/cases/' + id, updates, {
                headers: headers,
                timeout: NvConfig.timeoutMs
            }).then(function (res) {
                return res.data;
            }).catch(function (err) {
                return handleError(err, 'Update Case');
            });
        };

        service.linkCase = function (caseId, targetCaseId) {
            var headers = getHeaders();
            headers['Idempotency-Key'] = UtilsSrv.guid();

            return $http.post(baseUrl + '/cases/' + caseId + '/links', { target_case_id: targetCaseId }, {
                headers: headers,
                timeout: NvConfig.timeoutMs
            }).then(function (res) {
                return res.data;
            }).catch(function (err) {
                return handleError(err, 'Link Case');
            });
        };

        service.getCaseLinks = function (id) {
            return $http.get(baseUrl + '/cases/' + id + '/links', {
                headers: getHeaders(),
                timeout: NvConfig.timeoutMs
            }).then(function (res) {
                return res.data;
            }).catch(function (err) {
                return handleError(err, 'Case Links');
            });
        };

        service.createTask = function (caseId, task) {
            var headers = getHeaders();
            headers['Idempotency-Key'] = UtilsSrv.guid();

            return $http.post(baseUrl + '/case/' + caseId + '/task', task, {
                headers: headers,
                timeout: NvConfig.timeoutMs
            }).then(function (res) {
                return res.data;
            }).catch(function (err) {
                return handleError(err, 'Create Task');
            });
        };

        service.createTaskLog = function (taskId, log) {
            var headers = getHeaders();
            headers['Idempotency-Key'] = UtilsSrv.guid();

            return $http.post(baseUrl + '/tasks/' + taskId + '/logs', log, {
                headers: headers,
                timeout: NvConfig.timeoutMs
            }).then(function (res) {
                return res.data;
            }).catch(function (err) {
                return handleError(err, 'Create Task Log');
            });
        };

        // --- Evidence / Artifact Operations (Phase Z1.1) ---
        var artifactBaseUrl = NvConfig.nvArtifactBaseUrl || (baseUrl.replace('/api', '') + '/artifacts');

        service.getArtifacts = function (caseId) {
            return $http.get(artifactBaseUrl + '/case/' + caseId, {
                headers: getHeaders(),
                timeout: NvConfig.timeoutMs
            }).then(function (res) {
                return res.data;
            }).catch(function (err) {
                return handleError(err, 'Evidence List');
            });
        };

        service.uploadArtifact = function (caseId, file) {
            var fd = new FormData();
            fd.append('case_id', caseId);
            fd.append('file', file, file.name);

            var headers = getHeaders();
            headers['Content-Type'] = undefined; // Let browser set multipart boundary

            return $http.post(artifactBaseUrl + '/upload', fd, {
                headers: headers,
                transformRequest: angular.identity,
                timeout: NvConfig.timeoutMs * 5  // Allow longer for large files
            }).then(function (res) {
                return res.data;
            }).catch(function (err) {
                return handleError(err, 'Artifact Upload');
            });
        };

        service.getArtifactDownloadUrl = function (artifactId) {
            return $http.get(artifactBaseUrl + '/' + artifactId + '/download', {
                headers: getHeaders(),
                timeout: NvConfig.timeoutMs
            }).then(function (res) {
                return res.data;
            }).catch(function (err) {
                return handleError(err, 'Artifact Download');
            });
        };

        service.getSightings = function (sha256) {
            return $http.get(artifactBaseUrl + '/sightings/' + sha256, {
                headers: getHeaders(),
                timeout: NvConfig.timeoutMs
            }).then(function (res) {
                return res.data;
            }).catch(function (err) {
                return handleError(err, 'Sightings Lookup');
            });
        };

        // --- Graph (Phase E8.1 Visual Vyuha) ---
        service.getCaseGraph = function (caseId) {
            return $http.get(baseUrl + '/graph/case/' + encodeURIComponent(caseId), {
                headers: getHeaders(),
                timeout: NvConfig.timeoutMs
            }).then(function (res) {
                return res.data;
            }).catch(function (err) {
                return handleError(err, 'Case Graph');
            });
        };

        // Integration Hub — Node Service (Phase Z2.1)
        // Routed via Caddy: /node-service/* → nv-node-service:8085
        var nodeBaseUrl = '/node-service';

        service.getNodes = function (nodeType) {
            var params = nodeType ? '?node_type=' + nodeType : '';
            return $http.get(nodeBaseUrl + '/nodes' + params, {
                headers: getHeaders(), timeout: NvConfig.timeoutMs
            }).then(function (res) { return res.data; });
        };

        service.registerNode = function (data) {
            return $http.post(nodeBaseUrl + '/nodes', data, {
                headers: getHeaders(), timeout: NvConfig.timeoutMs
            }).then(function (res) { return res.data; });
        };

        service.updateNode = function (nodeId, patch) {
            return $http.patch(nodeBaseUrl + '/nodes/' + nodeId, patch, {
                headers: getHeaders(), timeout: NvConfig.timeoutMs
            }).then(function (res) { return res.data; });
        };

        service.testNode = function (nodeId) {
            return $http.post(nodeBaseUrl + '/nodes/' + nodeId + '/test', {}, {
                headers: getHeaders(), timeout: 20000  // Allow 20s for slow nodes
            }).then(function (res) { return res.data; });
        };

        // --- Health Check (Enterprise Dashboard) ---
        service.healthCheck = function () {
            return $http.get(baseUrl + '/status', {
                headers: getHeaders(),
                timeout: 5000
            }).then(function (res) {
                return res.data;
            }).catch(function () {
                return null;
            });
        };

        service.deleteNode = function (nodeId) {
            return $http.delete(nodeBaseUrl + '/nodes/' + nodeId, {
                headers: getHeaders(), timeout: NvConfig.timeoutMs
            }).then(function (res) { return res.data; });
        };

        // --- Tasks ---
        service.getTasks = function (caseId) {
            return $http.get(baseUrl + '/case/' + caseId + '/task', {
                headers: getHeaders(), timeout: NvConfig.timeoutMs
            }).then(function (res) { return res.data; }).catch(function (err) { return handleError(err, 'Tasks List'); });
        };

        service.getTask = function (taskId) {
            return $http.get(baseUrl + '/tasks/' + taskId, {
                headers: getHeaders(), timeout: NvConfig.timeoutMs
            }).then(function (res) { return res.data; }).catch(function (err) { return handleError(err, 'Task Detail'); });
        };

        service.getTaskLogs = function (taskId) {
            return $http.get(baseUrl + '/tasks/' + taskId + '/logs', {
                headers: getHeaders(), timeout: NvConfig.timeoutMs
            }).then(function (res) { return res.data; }).catch(function (err) { return handleError(err, 'Task Logs'); });
        };

        service.deleteTask = function (caseId, taskId) {
            return $http.delete(baseUrl + '/case/' + caseId + '/task/' + taskId, {
                headers: getHeaders(), timeout: NvConfig.timeoutMs
            }).then(function (res) { return res.data; }).catch(function (err) { return handleError(err, 'Delete Task'); });
        };

        service.updateTask = function (caseId, taskId, data) {
            return $http.patch(baseUrl + '/case/' + caseId + '/task/' + taskId, data, {
                headers: getHeaders(), timeout: NvConfig.timeoutMs
            }).then(function (res) { return res.data; }).catch(function (err) { return handleError(err, 'Update Task'); });
        };

        // --- Observables ---
        service.getObservables = function (caseId) {
            return $http.get(baseUrl + '/case/' + caseId + '/observable', {
                headers: getHeaders(), timeout: NvConfig.timeoutMs
            }).then(function (res) { return res.data; }).catch(function (err) { return handleError(err, 'Observables List'); });
        };

        service.createObservable = function (caseId, data) {
            return $http.post(baseUrl + '/case/' + caseId + '/observable', data, {
                headers: getHeaders(), timeout: NvConfig.timeoutMs
            }).then(function (res) { return res.data; }).catch(function (err) { return handleError(err, 'Create Observable'); });
        };

        service.deleteObservable = function (caseId, obsId) {
            return $http.delete(baseUrl + '/case/' + caseId + '/observable/' + obsId, {
                headers: getHeaders(), timeout: NvConfig.timeoutMs
            }).then(function (res) { return res.data; }).catch(function (err) { return handleError(err, 'Delete Observable'); });
        };

        service.updateObservable = function (caseId, obsId, data) {
            return $http.patch(baseUrl + '/case/' + caseId + '/observable/' + obsId, data, {
                headers: getHeaders(), timeout: NvConfig.timeoutMs
            }).then(function (res) { return res.data; }).catch(function (err) { return handleError(err, 'Update Observable'); });
        };

        // --- TTPs ---
        service.getTtps = function (caseId) {
            return $http.get(baseUrl + '/case/' + caseId + '/ttp', {
                headers: getHeaders(), timeout: NvConfig.timeoutMs
            }).then(function (res) { return res.data; }).catch(function (err) { return handleError(err, 'TTPs List'); });
        };

        service.addTtp = function (caseId, data) {
            return $http.post(baseUrl + '/case/' + caseId + '/ttp', data, {
                headers: getHeaders(), timeout: NvConfig.timeoutMs
            }).then(function (res) { return res.data; }).catch(function (err) { return handleError(err, 'Add TTP'); });
        };

        service.removeTtp = function (caseId, ttpId) {
            return $http.delete(baseUrl + '/case/' + caseId + '/ttp/' + ttpId, {
                headers: getHeaders(), timeout: NvConfig.timeoutMs
            }).then(function (res) { return res.data; }).catch(function (err) { return handleError(err, 'Remove TTP'); });
        };

        // --- Pages ---
        service.getPages = function (caseId) {
            return $http.get(baseUrl + '/case/' + caseId + '/page', {
                headers: getHeaders(), timeout: NvConfig.timeoutMs
            }).then(function (res) { return res.data; }).catch(function (err) { return handleError(err, 'Pages List'); });
        };

        return service;
    });
})();
