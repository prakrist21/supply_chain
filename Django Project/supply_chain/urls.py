from django.urls import path

from . import views

urlpatterns = [
    # path('', views.hello_world_index, name='index'),
    path('', views.landing_page, name='index'),
    path('councils', views.all_councils, name='councils'),
    path("login/",views.UserLogin.as_view(),name="login"),
    path("logout/",views.UserLogout.as_view(),name="logout"),
    path("register/",views.UserRegister.as_view(),name="register"),

    #dashboard
    path("councilDashboard/",views.CouncilDashboardView.as_view(),name="councilDashboard"),
    path("contractorDashboard/",views.ContractorDashboardView.as_view(),name="contractorDashboard"),

    #project and package
    path('projects/', views.project_list, name='project_list'),
    path('projects/create/', views.ProjectCreateView.as_view(), name='project_create'),
    path('projects/<int:project_id>/', views.project_detail, name='project_detail'),
    path('project/<int:project_id>/delete/', views.project_delete, name='project_delete'),
    path('project/<int:project_id>/end/', views.project_end, name='project_end'),
    path('packages/<int:package_id>/delete/', views.PackageDeleteView.as_view(), name='package_delete'),
    path('package/<int:package_id>/', views.PackageDetailView.as_view(), name='package_detail'),
    path('projects/<int:project_id>/package/add/', views.PackageCreateView.as_view(), name='package_add'),
    path('contractor/projects/', views.open_projects, name='open_projects'),
    path('contractor/projects/<int:project_id>/', views.ContractorProjectDetailView.as_view(),
         name='contractor_project_detail'),

    #bid
    path('packages/<int:package_id>/bid/', views.BidCreateView.as_view(), name='bid_create'),
    path('bid/<int:bid_id>/approve/', views.BidApproveView.as_view(), name='bid_approve'),
    path('bid/<int:bid_id>/reject/', views.BidRejectView.as_view(), name='bid_reject'),
    path('contractor/my_bids/', views.contractor_my_bids, name='contractor_my_bids'),
    path('council/all_bids/', views.council_all_bids, name='council_all_bids'),

    #team
    path('teams/', views.TeamListView.as_view(), name='team_list'),
    path('teams/<int:project_id>/', views.TeamDetailView.as_view(), name='team_detail'),

    #profile
    path('profile/', views.ProfileView.as_view(), name='profile_view'),
    path('profile/edit/', views.ProfileEditView.as_view(), name='profile_edit'),
    path('profile/password/', views.CustomPasswordChangeView.as_view(), name='password_change'),

    #reports
    path('council/reports/', views.council_reports, name='council_reports'),
    path('council/reports/download/<int:project_id>/', views.download_project_report, name='download_project_report'),

    #activity
    path('my-activity/', views.my_activity, name='my_activity'),
]
