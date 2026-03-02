(function () {
    'use strict';

    /* @ngInject */
    function CasePagesCtrl($scope, $http, $stateParams, NotificationSrv, caze) {
        var caseId = $stateParams.caseId;
        $scope.caze = caze;
        $scope.pages = [];
        $scope.isLoading = true;
        $scope.isEditing = false;

        $scope.newPage = {
            title: '',
            content: ''
        };

        // Fetch Case Pages
        function loadPages() {
            $scope.isLoading = true;
            $http.get('/api/case/' + caseId + '/page')
                .then(function (response) {
                    $scope.pages = response.data;
                })
                .catch(function (error) {
                    NotificationSrv.error('CasePagesCtrl', 'Failed to load pages: ' + (error.data && error.data.detail ? error.data.detail : error.statusText), error.status);
                })
                .finally(function () {
                    $scope.isLoading = false;
                });
        }

        // Create a New Page
        $scope.createPage = function () {
            if (!$scope.newPage.title || !$scope.newPage.content) {
                NotificationSrv.error('CasePagesCtrl', 'Title and content are required', 400);
                return;
            }

            $http.post('/api/case/' + caseId + '/page', $scope.newPage)
                .then(function (response) {
                    NotificationSrv.success('Page created successfully');
                    $scope.isEditing = false;
                    $scope.newPage = { title: '', content: '' };
                    loadPages();
                })
                .catch(function (error) {
                    NotificationSrv.error('CasePagesCtrl', 'Failed to create page: ' + (error.data && error.data.detail ? error.data.detail : error.statusText), error.status);
                });
        };

        // Delete a Page
        $scope.deletePage = function (pageId) {
            if (!confirm("Are you sure you want to delete this page?")) return;

            $http.delete('/api/case/' + caseId + '/page/' + pageId)
                .then(function () {
                    NotificationSrv.success('Page deleted successfully');
                    loadPages();
                })
                .catch(function (error) {
                    NotificationSrv.error('CasePagesCtrl', 'Failed to delete page: ' + (error.data && error.data.detail ? error.data.detail : error.statusText), error.status);
                });
        };

        // Init
        loadPages();
    }

    angular.module('theHiveControllers').controller('CasePagesCtrl', CasePagesCtrl);
})();
