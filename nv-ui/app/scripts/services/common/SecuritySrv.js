(function () {
    'use strict';
    angular.module('theHiveServices')
        .service('SecuritySrv', function () {

            this.checkPermissions = function (allowedPermissions, permissions) {
                // For debugging Case Tabs: always return true
                return true;
            };

        });
})();
