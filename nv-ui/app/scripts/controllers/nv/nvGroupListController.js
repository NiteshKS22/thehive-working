(function () {
    'use strict';

    angular.module('thehive').controller('NvGroupListCtrl', function ($scope, $state, $interval, NvApiSrv, VersionSrv) {
        var vm = this;

        // --- State ---
        vm.loading = true;
        vm.error = null;
        vm.groups = [];
        vm.total = 0;
        vm.lastRefreshed = null;
        vm.autoRefreshEnabled = true;
        vm.autoRefreshSeconds = 30;

        vm.stats = {
            totalIncidents: 0,
            openIncidents: 0,
            totalAlerts: 0,
            totalCases: 0
        };

        vm.systemVersion = '';
        vm.healthChecks = [
            { label: 'NeuralVyuha Engine', status: 'checking', detail: '' },
            { label: 'Query Service', status: 'checking', detail: '' },
            { label: 'Cases Database', status: 'checking', detail: '' },
            { label: 'Alert Pipeline', status: 'checking', detail: '' }
        ];

        vm.params = {
            size: 20,
            from_: 0,
            status: 'OPEN',
            severity: undefined
        };

        // --- Greeting ---
        vm.getGreeting = function () {
            var hour = new Date().getHours();
            if (hour < 12) return 'Good Morning';
            if (hour < 17) return 'Good Afternoon';
            return 'Good Evening';
        };
        vm.greeting = vm.getGreeting();

        // --- Load incident groups ---
        vm.load = function () {
            vm.loading = true;
            vm.error = null;
            NvApiSrv.getGroups(vm.params).then(function (data) {
                if (angular.isArray(data)) {
                    vm.groups = data;
                    vm.total = data.length;
                } else if (data) {
                    vm.groups = data.hits || data.groups || [];
                    vm.total = data.total || 0;
                } else {
                    vm.groups = [];
                    vm.total = 0;
                }
                vm.lastRefreshed = new Date();
            }).catch(function (err) {
                vm.groups = [];
                vm.total = 0;
                vm.error = 'Unable to load incidents. The server may be unreachable.';
            }).finally(function () {
                vm.loading = false;
            });
        };

        // --- Load dashboard stats ---
        vm.loadStats = function () {
            NvApiSrv.getGroups({ size: 1, from_: 0 }).then(function (data) {
                vm.stats.totalIncidents = (data && data.total) || 0;
            }).catch(function () { /* fail silently for stats */ });

            NvApiSrv.getGroups({ size: 1, from_: 0, status: 'OPEN' }).then(function (data) {
                vm.stats.openIncidents = (data && data.total) || 0;
            }).catch(function () { });

            NvApiSrv.getAlerts({ size: 1, from_: 0 }).then(function (data) {
                vm.stats.totalAlerts = (data && data.total) || 0;
            }).catch(function () { });

            // Note: getCases on the backend expects limit/offset instead of size/from_ because it uses Postgres directly in api.py
            NvApiSrv.getCases({ limit: 1, offset: 0 }).then(function (data) {
                vm.stats.totalCases = (data && data.total) || 0;
            }).catch(function () { });
        };

        // --- Load system health (dynamic) ---
        vm.loadHealth = function () {
            // Engine version
            VersionSrv.get().then(function (config) {
                vm.systemVersion = (config && config.versions && config.versions.TheHive) ? config.versions.TheHive : 'NeuralVyuha Zenith';
                vm.healthChecks[0].status = 'online';
                vm.healthChecks[0].detail = 'v' + vm.systemVersion;
            }).catch(function () {
                vm.healthChecks[0].status = 'offline';
                vm.healthChecks[0].detail = 'Unreachable';
            });

            // Query service
            NvApiSrv.healthCheck().then(function (data) {
                if (data) {
                    vm.healthChecks[1].status = 'online';
                    vm.healthChecks[1].detail = 'Operational';
                } else {
                    vm.healthChecks[1].status = 'offline';
                    vm.healthChecks[1].detail = 'Unreachable';
                }
            });

            // Cases database — try fetching 1 case
            NvApiSrv.getCases({ limit: 1, offset: 0 }).then(function () {
                vm.healthChecks[2].status = 'online';
                vm.healthChecks[2].detail = 'Connected';
            }).catch(function () {
                vm.healthChecks[2].status = 'offline';
                vm.healthChecks[2].detail = 'Disconnected';
            });

            // Alert pipeline — try fetching 1 alert
            NvApiSrv.getAlerts({ size: 1, from_: 0 }).then(function () {
                vm.healthChecks[3].status = 'online';
                vm.healthChecks[3].detail = 'Active';
            }).catch(function () {
                vm.healthChecks[3].status = 'offline';
                vm.healthChecks[3].detail = 'Inactive';
            });
        };

        // --- Filter by status ---
        vm.filterStatus = function (status) {
            vm.params.status = status;
            vm.params.from_ = 0;
            vm.load();
        };

        // --- Pagination ---
        vm.nextPage = function () {
            if (vm.params.from_ + vm.params.size < vm.total) {
                vm.params.from_ += vm.params.size;
                vm.load();
            }
        };

        vm.prevPage = function () {
            if (vm.params.from_ > 0) {
                vm.params.from_ = Math.max(0, vm.params.from_ - vm.params.size);
                vm.load();
            }
        };

        vm.getCurrentPage = function () {
            return Math.floor(vm.params.from_ / vm.params.size) + 1;
        };

        vm.getTotalPages = function () {
            return Math.max(1, Math.ceil(vm.total / vm.params.size));
        };

        // --- Open group detail ---
        vm.openGroup = function (group) {
            if (group && group.group_id) {
                $state.go('app.nv-group-detail', { id: group.group_id });
            }
        };

        // --- Retry after error ---
        vm.retry = function () {
            vm.error = null;
            vm.load();
            vm.loadStats();
            vm.loadHealth();
        };

        // --- Auto-refresh ---
        vm.toggleAutoRefresh = function () {
            vm.autoRefreshEnabled = !vm.autoRefreshEnabled;
            if (vm.autoRefreshEnabled) {
                startAutoRefresh();
            } else {
                stopAutoRefresh();
            }
        };

        var refreshInterval = null;
        function startAutoRefresh() {
            stopAutoRefresh();
            refreshInterval = $interval(function () {
                vm.load();
                vm.loadStats();
                vm.loadHealth();
            }, vm.autoRefreshSeconds * 1000);
        }

        function stopAutoRefresh() {
            if (refreshInterval) {
                $interval.cancel(refreshInterval);
                refreshInterval = null;
            }
        }

        // --- Severity helper ---
        vm.getSeverityLabel = function (severity) {
            if (severity >= 4) return 'CRITICAL';
            if (severity === 3) return 'HIGH';
            if (severity === 2) return 'MEDIUM';
            return 'LOW';
        };

        vm.getSeverityClass = function (severity) {
            if (severity >= 4) return 'nv-sev-critical';
            if (severity === 3) return 'nv-sev-high';
            if (severity === 2) return 'nv-sev-medium';
            return 'nv-sev-low';
        };

        // --- Cleanup on destroy ---
        $scope.$on('$destroy', function () {
            stopAutoRefresh();
        });

        // --- Initial load ---
        vm.load();
        vm.loadStats();
        vm.loadHealth();
        if (vm.autoRefreshEnabled) {
            startAutoRefresh();
        }
    });
})();
