from django.urls import path
from . import views

urlpatterns = [
    # General
    path('', views.index, name='index'),
    path('logout/', views.logout_view, name='logout'),

    # Teacher Auth & Views
    path('teacher/login/', views.teacher_login, name='teacher_login'),
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/game/create/', views.create_game_setup, name='create_game_setup'),
    path('teacher/game/<int:game_id>/questions/', views.setup_game_questions, name='setup_game_questions'),
    path('teacher/game/<int:game_id>/delete/', views.delete_game, name='delete_game'),
    path('teacher/game/<int:game_id>/toggle-active/', views.toggle_game_active, name='toggle_game_active'),
    path('teacher/game/<int:game_id>/insights/', views.game_insights, name='game_insights'),


    # Student Auth & Views
    path('student/register/', views.student_register, name='student_register'),
    path('student/login/', views.student_login, name='student_login'),
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('student/change-password/', views.student_change_password, name='student_change_password'),
    path('student/play/<int:game_id>/', views.play_game, name='play_game'),
    path('student/submit/<int:game_id>/', views.submit_score, name='submit_score'),
    path('student/result/<int:attempt_id>/', views.game_result, name='game_result'),
    path('student/certificate/<int:attempt_id>/', views.generate_certificate, name='generate_certificate'),
    path('student/feedback/submit/', views.submit_feedback, name='submit_feedback'),
    path('teacher/feedback/pdf/', views.download_feedback_pdf, name='download_feedback_pdf'),
    path('teacher/feedback/delete/', views.delete_all_feedback, name='delete_all_feedback'),
    path('teacher/unlock-replay/<int:student_id>/<int:game_id>/', views.unlock_student_replay, name='unlock_student_replay'),
    path('teacher/toggle-replay/<int:student_id>/<int:game_id>/', views.toggle_student_replay, name='toggle_student_replay'),
    path('teacher/unlock-all-replays/', views.unlock_all_student_replays, name='unlock_all_student_replays'),
    path('teacher/lock-all-replays/', views.lock_all_student_replays, name='lock_all_student_replays'),
    path('teacher/settings/update/', views.update_teacher_settings, name='update_teacher_settings'),

    # PDF Notes Routes
    path('teacher/notes/', views.manage_notes, name='manage_notes'),
    path('teacher/notes/<int:note_id>/edit/', views.edit_note, name='edit_note'),
    path('teacher/notes/<int:note_id>/delete/', views.delete_note, name='delete_note'),

    # Student Marks Routes
    path('teacher/marks/', views.manage_marks, name='manage_marks'),
    path('teacher/marks/<int:mark_id>/edit/', views.edit_mark, name='edit_mark'),
    path('teacher/marks/<int:mark_id>/delete/', views.delete_mark, name='delete_mark'),
    path('teacher/marks/delete-all/', views.delete_all_marks, name='delete_all_marks'),

    # Redesigned Dashboard View URLs
    path('teacher/games/', views.view_games, name='view_games'),
    path('teacher/students/', views.view_students, name='view_students'),
    path('teacher/students/manage/', views.manage_students, name='manage_students'),
    path('teacher/students/create/', views.create_student, name='create_student'),
    path('teacher/students/<int:student_id>/edit/', views.edit_student, name='edit_student'),
    path('teacher/students/<int:student_id>/profile/', views.student_profile, name='student_profile'),
    path('teacher/students/<int:student_id>/delete/', views.delete_student, name='delete_student'),
    path('teacher/announcements/', views.manage_announcements, name='manage_announcements'),
    path('teacher/announcements/<int:announcement_id>/delete/', views.delete_announcement, name='delete_announcement'),
    path('teacher/feedback/<int:feedback_id>/delete/', views.delete_feedback, name='delete_feedback'),
    path('teacher/feedback/<int:feedback_id>/toggle-read/', views.toggle_feedback_read, name='toggle_feedback_read'),

    # Student Game Creation & Approval Routes
    path('teacher/students/<int:student_id>/toggle-creation/', views.toggle_student_game_creation, name='toggle_student_game_creation'),
    path('teacher/student-games/', views.review_student_games, name='review_student_games'),
    path('teacher/student-games/<int:game_id>/approve/', views.approve_student_game, name='approve_student_game'),
    path('teacher/student-games/<int:game_id>/reject/', views.reject_student_game, name='reject_student_game'),
    path('student/games/create/', views.student_create_game_setup, name='student_create_game_setup'),
    path('student/games/<int:game_id>/questions/', views.student_setup_game_questions, name='student_setup_game_questions'),
    path('student/games/<int:game_id>/submit/', views.student_submit_game, name='student_submit_game'),

    # Redesigned Student Dashboard subsections
    path('student/games/', views.student_view_games, name='student_view_games'),
    path('student/marks/', views.student_view_marks, name='student_view_marks'),
    path('student/notes/', views.student_view_notes, name='student_view_notes'),
    path('student/feedback/', views.student_send_feedback, name='student_send_feedback'),
    path('student/performance/', views.student_performance_analysis, name='student_performance_analysis'),
]
