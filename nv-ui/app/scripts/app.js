'use strict';

// Define sub-modules first to ensure they exist for other scripts
angular.module('theHiveControllers', ['theHiveServices']);
angular.module('theHiveServices', []);
angular.module('theHiveDirectives', []);
angular.module('theHiveFilters', []);
angular.module('theHiveComponents', []);
angular.module('theHive', []);

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
    'angular-markdown-editor',
    'ui.ace',
    'angular-page-loader',
    'images-resizer',
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
    'theHiveFilters',
    'theHiveComponents',
    'theHive'
])
    .factory('UrlParser', function () {
        // Dummy factory injected for legacy v4 compatibility
        return {
            parse: function (url) { return url; }
        };
    })
    .factory('appConfig', function (VersionSrv, $q) {
        // Global appConfig service - wraps VersionSrv.get() with a safe fallback
        var defaultConfig = {
            config: {
                capabilities: [],
                pollingDuration: 3000,
                authType: [],
                ssoAutoLogin: false,
                protectDownloadsWith: null,
                freeTagDefaultColour: '#000000'
            },
            connectors: {
                cortex: { enabled: false, servers: [] },
                misp: { enabled: false, servers: [] }
            },
            versions: { TheHive: 'NeuralVyuha' },
            schemaStatus: 'OK'
        };

        return VersionSrv.get().then(function (config) {
            return config;
        }, function () {
            // If backend is unavailable, return safe defaults
            return defaultConfig;
        });
    })
    .config(function ($stateProvider, $urlRouterProvider, $httpProvider, NotificationProvider) {
        // Default route
        $urlRouterProvider.otherwise('/nv/dashboard');

        // Ensure parent case route cleanly redirects to details regardless of the UUID format
        $urlRouterProvider.when(/^\/case\/([a-zA-Z0-9_\-]+)$/i, '/case/$1/details');

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
                controller: 'AuthenticationCtrl',
                resolve: {
                    appConfig: function (appConfig) {
                        return appConfig;
                    }
                }
            })
            .state('app', {
                abstract: true,
                templateUrl: 'views/app.html',
                controller: 'RootCtrl',
                resolve: {
                    currentUser: function (AuthenticationSrv, $q) {
                        return AuthenticationSrv.current().catch(function (err) {
                            return $q.reject(err);
                        });
                    },
                    appConfig: function (appConfig) {
                        return appConfig;
                    }
                }
            })
            .state('app.index', {
                url: '/nv/dashboard',
                templateUrl: 'views/nv/nvGroupList.html',
                controller: 'NvGroupListCtrl',
                controllerAs: 'vm'
            })
            // Phase 3 — Enterprise Upgrade Restorations
            .state('app.alerts', {
                url: '/nv/alerts',
                templateUrl: 'views/nv/nvAlerts.html',
                controller: 'NvAlertListCtrl',
                controllerAs: 'vm'
            })
            .state('app.cases', {
                url: '/nv/cases',
                templateUrl: 'views/nv/nvCases.html',
                controller: 'NvCaseListCtrl',
                controllerAs: 'vm'
            })
            // Legacy / Active Direct Links
            .state('app.case', {
                url: '/case/:caseId',
                templateUrl: 'views/app.case.html',
                controller: 'CaseMainCtrl',
                resolve: {
                    caze: function (CaseSrv, $stateParams) {
                        return CaseSrv.getById($stateParams.caseId, true);
                    }
                }
            })
            .state('app.case.details', {
                url: '/details',
                templateUrl: 'views/partials/case/case.details.html',
                controller: 'CaseDetailsCtrl',
                data: { tab: 'details' }
            })
            .state('app.case.pages', {
                url: '/pages',
                templateUrl: 'views/partials/case/case.pages.html',
                controller: 'CasePagesCtrl',
                data: { tab: 'pages' }
            })
            .state('app.case.tasks', {
                url: '/tasks',
                templateUrl: 'views/partials/case/case.tasks.html',
                controller: 'CaseTasksCtrl',
                data: { tab: 'tasks' }
            })
            .state('app.case.tasks-item', {
                url: '/tasks/:itemId',
                templateUrl: 'views/partials/case/case.tasks.item.html',
                controller: 'CaseTasksItemCtrl',
                data: { tab: 'tasks' }
            })
            .state('app.case.observables', {
                url: '/observables',
                templateUrl: 'views/partials/case/case.observables.html',
                controller: 'CaseObservablesCtrl',
                data: { tab: 'observables' }
            })
            .state('app.case.observables-item', {
                url: '/observables/:itemId',
                templateUrl: 'views/partials/case/case.observables.item.html',
                controller: 'CaseObservablesItemCtrl',
                data: { tab: 'observables' }
            })
            .state('app.case.sharing', {
                url: '/sharing',
                templateUrl: 'views/partials/case/case.sharing.html',
                controller: 'CaseSharingCtrl',
                data: { tab: 'sharing' }
            })
            .state('app.case.procedures', {
                url: '/procedures',
                templateUrl: 'views/partials/case/case.ttps.html',
                controller: 'CaseTtpsCtrl',
                data: { tab: 'procedures' }
            })
            // Phase U1 — Zenith: Visual Vyuha Route
            .state('app.graph', {
                url: '/nv/graph/:caseId',
                templateUrl: 'views/nv/visual-vyuha.html',
                controller: 'nvVisualVyuhaCtrl',
                controllerAs: 'vm'
            })
            .state('app.admin', {
                url: '/nv/admin',
                templateUrl: 'views/nv/nvAdmin.html',
                controller: 'NvAdminCtrl',
                controllerAs: 'vm'
            })
            .state('app.profile', {
                url: '/nv/profile',
                templateUrl: 'views/nv/nvProfile.html',
                controller: 'NvProfileCtrl',
                controllerAs: 'vm'
            })
            .state('app.integrations', {
                url: '/nv/integrations',
                templateUrl: 'views/nv/integrations.html',
                controller: 'NvIntegrationsCtrl',
                controllerAs: 'vm'
            })
            .state('app.nv-help', {
                url: '/nv/help',
                templateUrl: 'views/nv/help.html',
                controller: 'NvHelpCtrl',
                controllerAs: 'vm'
            });
    })
    .run(function ($rootScope, $state, AuthenticationSrv, NvConfig) {
        // Initialization logic
        $rootScope.$on('$stateChangeStart', function (event, toState) {
            // Allow transition to proceed. If AuthenticationSrv.currentUser is missing,
            // the 'app' state's resolve block for 'currentUser' will catch it,
            // call AuthenticationSrv.current(), and if that fails, RootCtrl will redirect to login.
            if (toState.name === 'login' && AuthenticationSrv.currentUser) {
                event.preventDefault();
                $state.go('app.index');
            }
        });
    });
