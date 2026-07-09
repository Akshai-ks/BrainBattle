from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Subject, Student, Game, MCQQuestion, GameAttempt, WordPuzzleQuestion, AnonymousFeedback

class EducationalPlatformTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create a test teacher User
        self.teacher_user = User.objects.create_user(
            username='testteacher',
            email='teacher@test.com',
            password='securepassword123'
        )
        
        # Create a test subject
        self.subject = Subject.objects.create(name='Science')
        
        # Create a test student
        from django.contrib.auth.hashers import make_password
        self.student = Student.objects.create(
            name='John Doe',
            register_number='REG100',
            email='john@student.com',
            password=make_password('REG100@REG100')
        )

        # Create a test game
        self.game = Game.objects.create(
            title='Photosynthesis Challenge',
            subject=self.subject,
            game_type='word_puzzle',
            instructions='Solve the puzzle.',
            explanation='It is green.',
            created_by=self.teacher_user,
            is_active=True
        )

        # Create a test WordPuzzleQuestion related to the test game
        self.wp_question = WordPuzzleQuestion.objects.create(
            game=self.game,
            correct_word='CHLOROPHYLL',
            clue1='Green pigment in leaves',
            clue1_time=15,
            clue2='Starts with CH',
            clue2_time=30,
            full_marks=10,
            reduced_marks_clue1=7,
            min_marks_clue2=4
        )

    def test_homepage_redirects(self):
        """Test that homepage resolves and redirects guest users to login/welcome page."""
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'game_core/index.html')

    def test_teacher_login(self):
        """Test teacher login form validation and redirect."""
        response = self.client.post(reverse('teacher_login'), {
            'username': 'testteacher',
            'password': 'securepassword123'
        })
        self.assertRedirects(response, reverse('teacher_dashboard'))

    def test_student_login_success(self):
        """Test student login validation with matching register number and password."""
        response = self.client.post(reverse('student_login'), {
            'register_number': 'REG100',
            'password': 'REG100@REG100'
        })
        self.assertRedirects(response, reverse('student_dashboard'))
        self.assertEqual(self.client.session['student_id'], self.student.id)

    def test_student_login_failure(self):
        """Test student login validation failure handles invalid credentials."""
        response = self.client.post(reverse('student_login'), {
            'register_number': 'REG999',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        # Session should not contain student details
        self.assertNotIn('student_id', self.client.session)

    def test_submit_score_ajax(self):
        """Test AJAX score submission logs game attempts."""
        # Login student
        session = self.client.session
        session['student_id'] = self.student.id
        session['student_name'] = self.student.name
        session.save()

        # Submit score
        response = self.client.post(reverse('submit_score', args=[self.game.id]), {
            'score': 7,
            'max_score': 10,
            'clues_used': 1,
            'time_taken': 20
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        
        # Verify attempt exists in database
        attempt = GameAttempt.objects.get(id=data['attempt_id'])
        self.assertEqual(attempt.student, self.student)
        self.assertEqual(attempt.game, self.game)
        self.assertEqual(attempt.score, 7)
        self.assertEqual(attempt.max_score, 10)
        self.assertEqual(attempt.clues_used, 1)
        self.assertEqual(attempt.time_taken, 20)

    def test_certificate_eligibility(self):
        """Test certificates are only accessible for perfect scores."""
        # Login student
        session = self.client.session
        session['student_id'] = self.student.id
        session['student_name'] = self.student.name
        session.save()

        # Attempt 1: Less than perfect score (7/10)
        attempt_fail = GameAttempt.objects.create(
            student=self.student,
            game=self.game,
            score=7,
            max_score=10,
            clues_used=1,
            time_taken=20
        )
        
        response = self.client.get(reverse('generate_certificate', args=[attempt_fail.id]))
        # Should redirect to results page
        self.assertRedirects(response, reverse('game_result', args=[attempt_fail.id]))

        # Attempt 2: Perfect score (10/10)
        attempt_success = GameAttempt.objects.create(
            student=self.student,
            game=self.game,
            score=10,
            max_score=10,
            clues_used=0,
            time_taken=12
        )
        
        response = self.client.get(reverse('generate_certificate', args=[attempt_success.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'game_core/certificate.html')

    def test_create_game_default_subject(self):
        """Test creating a game automatically assigns the default 'General' subject."""
        self.client.force_login(self.teacher_user)
        response = self.client.post(reverse('create_game_setup'), {
            'title': 'New Game',
            'game_type': 'mcq',
            'instructions': 'Play.',
            'explanation': 'Explanation.'
        })
        self.assertEqual(response.status_code, 302)
        game = Game.objects.get(title='New Game')
        self.assertEqual(game.subject.name, 'General')

    def test_anonymous_feedback(self):
        """Test student submitting anonymous feedback and teacher viewing/downloading it."""
        # 1. Login student
        session = self.client.session
        session['student_id'] = self.student.id
        session['student_name'] = self.student.name
        session.save()

        # 2. Submit anonymous feedback
        response = self.client.post(reverse('submit_feedback'), {
            'message': 'Great platform, but please add more Chemistry games!'
        })
        self.assertRedirects(response, reverse('student_dashboard'))
        
        # Verify feedback exists in database and has no reference to student
        feedback = AnonymousFeedback.objects.get(teacher=self.teacher_user)
        self.assertEqual(feedback.message, 'Great platform, but please add more Chemistry games!')
        # Ensure it has NO student field (strictly anonymous)
        self.assertFalse(hasattr(feedback, 'student'))

        # 3. Login teacher
        self.client.force_login(self.teacher_user)

        # 4. View dashboard (contains feedback_list)
        response = self.client.get(reverse('teacher_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(feedback, response.context['feedback_list'])

        # 5. Download feedback PDF
        response = self.client.get(reverse('download_feedback_pdf'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['content-type'], 'application/pdf')
        self.assertIn(b"%PDF-1.4", response.content)
        self.assertIn(b"Chemistry games", response.content)

        # 6. Delete all feedback
        response = self.client.post(reverse('delete_all_feedback'))
        self.assertRedirects(response, reverse('teacher_dashboard'))
        self.assertEqual(AnonymousFeedback.objects.filter(teacher=self.teacher_user).count(), 0)

    def test_inactive_game_not_shown_or_playable(self):
        """Test that inactive games are not displayed to students and cannot be played directly."""
        # Create an inactive game
        inactive_game = Game.objects.create(
            title='Inactive Challenge',
            subject=self.subject,
            game_type='word_puzzle',
            instructions='Solve this.',
            explanation='Answer.',
            created_by=self.teacher_user,
            is_active=False
        )
        
        # Log in student
        session = self.client.session
        session['student_id'] = self.student.id
        session['student_name'] = self.student.name
        session.save()
        
        # 1. View student dashboard - inactive game should NOT be in the games list
        response = self.client.get(reverse('student_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(inactive_game, response.context['games'])
        
        # 2. Attempt to play inactive game - should redirect with error
        response = self.client.get(reverse('play_game', args=[inactive_game.id]))
        self.assertRedirects(response, reverse('student_dashboard'))
        
    def test_toggle_game_active_view(self):
        """Test that teacher can toggle game active state."""
        self.client.force_login(self.teacher_user)
        
        # Game starts active (from setUp)
        self.assertTrue(self.game.is_active)
        
        # Toggle to inactive
        response = self.client.get(reverse('toggle_game_active', args=[self.game.id]))
        self.assertRedirects(response, reverse('teacher_dashboard'))
        self.game.refresh_from_db()
        self.assertFalse(self.game.is_active)
        
        # Toggle back to active
        response = self.client.get(reverse('toggle_game_active', args=[self.game.id]))
        self.assertRedirects(response, reverse('teacher_dashboard'))
        self.game.refresh_from_db()
        self.assertTrue(self.game.is_active)

    def test_student_register_is_disabled(self):
        """Test that open student registration redirects to login with error."""
        response = self.client.post(reverse('student_register'), {
            'name': 'New Student',
            'register_number': 'REG105',
            'email': 'new@student.com'
        })
        self.assertRedirects(response, reverse('student_login'))
        
    def test_teacher_manage_students_view(self):
        """Test teacher management interface manually creates student."""
        self.client.force_login(self.teacher_user)
        
        # 1. Access student management dashboard
        response = self.client.get(reverse('manage_students'))
        self.assertEqual(response.status_code, 200)
        
        # 2. Add student manually
        response = self.client.post(reverse('manage_students'), {
            'action': 'manual',
            'name': 'Bob Vance',
            'register_number': 'REG200'
        })
        self.assertRedirects(response, reverse('manage_students'))
        
        # Verify student exists with hashed password REG200@REG200
        student = Student.objects.get(register_number='REG200')
        self.assertEqual(student.name, 'Bob Vance')
        from django.contrib.auth.hashers import check_password
        self.assertTrue(check_password('REG200@REG200', student.password))

    def test_student_change_password_success(self):
        """Test successful student password change logs out the student and hashes the new password."""
        # 1. Login student
        session = self.client.session
        session['student_id'] = self.student.id
        session['student_name'] = self.student.name
        session.save()

        # 2. Change password
        response = self.client.post(reverse('student_change_password'), {
            'current_password': 'REG100@REG100',
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123'
        })
        self.assertRedirects(response, reverse('student_login'))

        # 3. Check password in db
        self.student.refresh_from_db()
        from django.contrib.auth.hashers import check_password
        self.assertTrue(check_password('newpassword123', self.student.password))
        
        # 4. Check session is flushed
        self.assertNotIn('student_id', self.client.session)

    def test_student_change_password_incorrect_current(self):
        """Test password change fails when current password is incorrect."""
        session = self.client.session
        session['student_id'] = self.student.id
        session['student_name'] = self.student.name
        session.save()

        response = self.client.post(reverse('student_change_password'), {
            'current_password': 'wrongcurrentpassword',
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123'
        })
        self.assertEqual(response.status_code, 200) # Re-renders page
        
        # Password should NOT change in db
        self.student.refresh_from_db()
        from django.contrib.auth.hashers import check_password
        self.assertTrue(check_password('REG100@REG100', self.student.password))

    def test_student_change_password_mismatch(self):
        """Test password change fails when new passwords do not match."""
        session = self.client.session
        session['student_id'] = self.student.id
        session['student_name'] = self.student.name
        session.save()

        response = self.client.post(reverse('student_change_password'), {
            'current_password': 'REG100@REG100',
            'new_password': 'newpassword123',
            'confirm_password': 'mismatchpassword'
        })
        self.assertEqual(response.status_code, 200) # Re-renders page
        
        # Password should NOT change in db
        self.student.refresh_from_db()
        from django.contrib.auth.hashers import check_password
        self.assertTrue(check_password('REG100@REG100', self.student.password))


