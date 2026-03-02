(function () {
    'use strict';

    angular.module('thehive').controller('NvAlertListCtrl', function ($scope, $state, NvApiSrv) {
        var vm = this;

        vm.loading = true;
        vm.error = null;
        vm.alerts = [];
        vm.total = 0;

        vm.params = {
            size: 20,
            from_: 0,
            status: 'New'
        };

        vm.load = function () {
            vm.loading = true;
            vm.error = null;
            NvApiSrv.getAlerts(vm.params).then(function (data) {
                if (angular.isArray(data)) {
                    vm.alerts = data;
                    vm.total = data.length;
                } else if (data) {
                    vm.alerts = data.data || data.hits || data.alerts || [];
                    vm.total = data.total || 0;
                } else {
                    vm.alerts = [];
                    vm.total = 0;
                }
            }).catch(function (err) {
                vm.alerts = [];
                vm.total = 0;
                vm.error = 'Unable to load alerts. The server may be unreachable.';
            }).finally(function () {
                vm.loading = false;
            });
        };

        vm.filterStatus = function (status) {
            vm.params.status = status;
            vm.params.from_ = 0;
            vm.load();
        };

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

        vm.retry = function () {
            vm.load();
        };

        vm.load();
    });
})();
