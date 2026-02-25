(function() {
    'use strict';
    angular.module('theHiveServices')
        .service('CaseSrv', function($q, $http, $resource, QuerySrv, NvApiSrv, NvConfig, NvRouter, PaginatedQuerySrv) {

            var resource = $resource('./api/case/:caseId', {}, {
                update: { method: 'PATCH' },
                links: { method: 'GET', url: './api/case/:caseId/links', isArray: true },
                forceRemove: { method: 'DELETE', url: './api/case/:caseId/force', params: { caseId: '@caseId' } },
                query: { method: 'POST', url: './api/case/_search', isArray: true }
            });

            this.get = resource.get;
            this.alerts = resource.alerts;
            this.forceRemove = resource.forceRemove;
            this.links = resource.links;
            this.update = resource.update;
            this.merge = resource.merge;
            this.query = resource.query;

            // --- Phase E6.4: Write-Path Override (Create Case) ---
            var originalSave = resource.save;
            this.save = function(params, data, success, error) {
                 // Handle optional params
                if (arguments.length === 3 && angular.isFunction(data)) {
                    error = success;
                    success = data;
                    data = params;
                    params = {};
                }

                if (NvConfig.MASTER_WRITE_TARGET === 'NV') {
                    // NV Path: Call NvApiSrv.createCase
                    // We must return a promise object that mimics $resource promise if possible
                    // However, controller usually relies on callback or promise chain.
                    return NvApiSrv.createCase(data).then(function(res) {
                        var ret = angular.extend({}, data, { _id: res.case_id, id: res.case_id });
                        if (angular.isFunction(success)) success(ret);
                        return ret;
                    }, function(err) {
                        if (angular.isFunction(error)) error(err);
                        return $q.reject(err);
                    });
                } else {
                    return originalSave(params, data, success, error);
                }
            };

            // --- Phase E6.3: NeuralVyuha List Adapter ---
            var NvCaseListAdapter = function(config, callback) {
                var self = this;
                this.values = [];
                this.total = 0;
                this.loading = false;
                this.config = config;

                this.update = function() {
                    self.loading = true;
                    var params = {
                        limit: config.pageSize || 15,
                        offset: 0
                    };

                    NvApiSrv.getCases(params).then(function(data) {
                        var mapped = _.map(data.cases || [], function(c) {
                            return {
                                _id: c.case_id,
                                title: c.title,
                                description: c.description,
                                severity: c.severity,
                                status: c.status,
                                owner: c.assigned_to,
                                startDate: c.created_at,
                                endDate: c.closed_at,
                                _source: 'NV'
                            };
                        });

                        self.values = mapped;
                        self.total = data.total;
                        if (angular.isFunction(config.onUpdate)) config.onUpdate(self.values);

                    }).catch(function(err) {
                        if (NvConfig.fallbackToV4) {
                            console.warn("NV Case List failed, falling back to v4", err);
                            QuerySrv.call('v1', [{ '_name': 'listCase' }], {
                                name: 'cases-fallback',
                                page: { from: 0, to: config.pageSize || 15 }
                            }).then(function(res) {
                                self.values = res;
                                self.total = res.length;
                                if (angular.isFunction(config.onUpdate)) config.onUpdate(self.values);
                            });
                        }
                    }).finally(function() {
                        self.loading = false;
                    });
                };

                this.update();
            };

            this.list = function(config, callback) {
                if (NvConfig.useNvQueryReads) {
                    return new NvCaseListAdapter(config, callback);
                }
                return new PaginatedQuerySrv(config, callback);
            };

            this.getById = function(id, withStats) {
                var defer = $q.defer();
                var fetchLegacy = function() {
                    QuerySrv.call('v1', [{ '_name': 'getCase', 'idOrName': id }], {
                        name:'get-case-' + id,
                        page: { from: 0, to: 1, extraData: withStats ? [ "observableStats", "taskStats", "alerts", "isOwner", "shareCount", "permissions" ] : [] }
                    }).then(function(response) { defer.resolve(response[0]); }).catch(function(err){ defer.reject(err); });
                };

                if (NvConfig.useNvQueryReads) {
                    NvApiSrv.getCase(id).then(function(nvCase) {
                        var legacyCase = {
                            _id: nvCase.case_id,
                            title: nvCase.title,
                            description: nvCase.description,
                            severity: nvCase.severity,
                            status: nvCase.status,
                            owner: nvCase.assigned_to,
                            startDate: nvCase.created_at,
                            endDate: nvCase.closed_at,
                            tags: [], customFields: {}, _source: 'NV'
                        };
                        defer.resolve(legacyCase);
                    }).catch(function(err) {
                        if (NvConfig.fallbackToV4) { fetchLegacy(); } else { defer.reject(err); }
                    });
                } else { fetchLegacy(); }
                return defer.promise;
            };

            this.alerts = function(id) {
                var defer = $q.defer();
                QuerySrv.call('v1', [{ '_name': 'getCase', 'idOrName': id }, {'_name': 'alerts'}], { name:'get-case-alerts' + id })
                    .then(function(response) { defer.resolve(response); })
                    .catch(function(err){ defer.reject(err); });
                return defer.promise;
            };

            this.merge = function(ids) { return $http.post('./api/v1/case/_merge/' + ids.join(',')); };
            this.bulkUpdate = function(ids, update) { return $http.patch('./api/case/_bulk', _.extend({ids: ids}, update)); };
            this.getShares = function(id) { return $http.get('./api/case/' + id + '/shares'); };
            this.setShares = function(id, shares) { return $http.post('./api/case/' + id + '/shares', { "shares": shares }); };
            this.updateShare = function(org, patch) { return $http.patch('./api/case/share/' + org, patch); };
            this.removeShare = function(id, share) { return $http.delete('./api/case/'+id+'/shares', { data: { organisations: [share.organisationName] }, headers: { 'Content-Type': 'application/json' } }); };
            this.removeCustomField = function(customfFieldValueId) { return $http.delete('./api/v1/case/customField/' + customfFieldValueId) }
        });
})();
