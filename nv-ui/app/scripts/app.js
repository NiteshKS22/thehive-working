'use strict';

// Define sub-modules first to ensure they exist for other scripts
angular.module('theHiveControllers', []);
angular.module('theHiveServices', []);
angular.module('theHiveDirectives', []);
angular.module('theHiveFilters', []);

angular.module('thehive', [
    'ngAnimate',
    'ngCookies',
    'ngResource',
    'ngSanitize',
    'ngTouch',
    'ngMessages',
    'ui.bootstrap',
    'ui.router',
    'ui-notification',
    'LocalStorageModule',
    'angularMoment',
    'timer',
    'ngTagsInput',
    'ngFileUpload',
    'angular-clipboard',
    'hc.marked',
    'hljs',
    'angularMarkdownEditor',
    'ui.ace',
    'angular-page-loader',
    'imagesResizer',
    'naif.base64',
    'ui.sortable',
    'duScroll',
    'dndLists',
    'colorpicker.module',
    'btorfs.multiselect',
    'ja.qr',
    'theHiveControllers',
    'theHiveServices',
    'theHiveDirectives',
    'theHiveFilters'
])
    .config(function ($stateProvider, $urlRouterProvider, $httpProvider, NotificationProvider) {
        // Default route
        $urlRouterProvider.otherwise('/nv/dashboard');

        NotificationProvider.setOptions({
            delay: 5000,
            startTop: 20,
            startRight: 10,
            verticalSpacing: 20,
            horizontalSpacing: 20,
            positionX: 'right',
            positionY: 'top'
        });

        $stateProvider
            .state('login', {
                url: '/login',
                templateUrl: 'views/login.html',
                controller: 'AuthenticationCtrl'
            })
            .state('app', {
                abstract: true,
                templateUrl: 'views/app.html',
                controller: 'RootCtrl',
                resolve: {
                    currentUser: function (AuthenticationSrv) {
                        return AuthenticationSrv.current();
                    },
                    appConfig: function (VersionSrv) {
                        return VersionSrv.config();
                    }
                }
            })
            .state('app.index', {
                url: '/nv/dashboard',
                templateUrl: 'views/nv/nvGroupList.html',
                controller: 'nvGroupListController',
                controllerAs: 'vm'
            })
            .state('app.nv-help', {
                url: '/nv/help',
                templateUrl: 'views/nv/help.html',
                controller: 'NvHelpCtrl',
                controllerAs: 'vm'
            })
            .state('app.integrations', {
                url: '/nv/integrations',
                templateUrl: 'views/nv/integrations.html',
                controller: 'nvIntegrationsCtrl',
                controllerAs: 'vm'
            })
            .state('app.case', {
                url: '/case/:caseId',
                templateUrl: 'views/app.case.html',
                controller: 'CaseDetailsCtrl'
            });
    })
    .run(function ($rootScope, $state, AuthenticationSrv, NvConfig, appConfig) {
        // Initialization logic
        $rootScope.$on('$stateChangeStart', function (event, toState) {
            if (toState.name !== 'login' && !AuthenticationSrv.isAuthenticated()) {
                // Simplified for now to avoid blocking bootstrap
                // event.preventDefault();
                // $state.go('login');
            }
        });
    });
