from django.urls import path
from . import views

urlpatterns = [
    # Main pages
    path('', views.main_page, name='main_page'),
    path('notifications/', views.notification_page, name='notification_page'),
    path('notification_page/', views.notification_page, name='notification_page'),
    path('renewals/', views.renewal_notices_page, name='renewal_notices_page'),
    path('renewals/dismiss/<int:notice_pk>/', views.dismiss_renewal, name='dismiss_renewal'), 
    path('customer_list/', views.customer_list, name='customer_list'),

    # Customer CRUD
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/<str:pk>/', views.customer_detail, name='customer_detail'),
    path('customers/<str:customer_pk>/upload_file/', views.upload_customer_file, name='upload_customer_file'),
    path('delete_file/<int:file_pk>/', views.delete_customer_file, name='delete_customer_file'),
    path('add_customer/', views.add_customer, name='add_customer'),
    path('edit_customer/<str:pk>/', views.edit_customer, name='edit_customer'),
    path('delete_customer/<str:pk>/', views.delete_customer, name='delete_customer'),

    # Insurance CRUD
    path('add_insurance/', views.add_insurance, name='add_insurance'),
    path('edit_insurance/<str:pk>/', views.edit_insurance, name='edit_insurance'),
    path('insurance/<str:pk>/delete/', views.delete_insurance, name='delete_insurance'),

    # Warranty CRUD
    path('add_warranty/<str:customer_pk>/', views.add_warranty, name='add_warranty'),
    path('edit_warranty/<int:pk>/', views.edit_warranty, name='edit_warranty'),
    path('delete_warranty/<int:pk>/', views.delete_warranty, name='delete_warranty'),

    # Defect CRUD
    path('add_defect/<str:customer_pk>/', views.add_defect, name='add_defect'),
    path('edit_defect/<int:pk>/', views.edit_defect, name='edit_defect'),
    path('delete_defect/<int:pk>/', views.delete_defect, name='delete_defect'),

    path('defects/', views.defect_list, name='defect_list'),
    path('defects/add/', views.add_defect_record, name='add_defect_record'),
    path('defects/solve/<int:pk>/', views.solve_defect, name='solve_defect'),
    path('defects/edit/<int:pk>/', views.edit_defect_record, name='edit_defect_record'),
    path('defects/delete/<int:pk>/', views.delete_defect_record, name='delete_defect_record'),
]
