(function () {
    'use strict';

    angular.module('theHive').controller('NvGroupListCtrl', function ($scope, NvApiSrv) {
        var vm = this;
        vm.loading = true;
        vm.groups = [];
        vm.total = 0;
        vm.params = {
            limit: 20,
            offset: 0,
            status: 'OPEN', // Default filter
            severity: undefined
        };

        vm.load = function () {
            vm.loading = true;
            NvApiSrv.getGroups(vm.params).then(function (data) {
                // The API response structure for /groups needs to be verified. Assuming { total: N, groups: [...] }
                // If it returns a list directly, adapt.
                if (angular.isArray(data)) {
                     vm.groups = data;
                     vm.total = data.length;
                } else {
                     vm.groups = data.groups || [];
                     vm.total = data.total || 0;
                }
            }).finally(function () {
                vm.loading = false;
            });
        };

        vm.nextPage = function () {
            if (vm.params.offset + vm.params.limit < vm.total) {
                vm.params.offset += vm.params.limit;
                vm.load();
            }
        };

        vm.prevPage = function () {
            if (vm.params.offset > 0) {
                vm.params.offset = Math.max(0, vm.params.offset - vm.params.limit);
                vm.load();
            }
        };

        // Initial load
        vm.load();
    });
})();
