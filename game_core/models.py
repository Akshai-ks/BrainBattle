from django.db import models
from django.contrib.auth.models import User

class Subject(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Student(models.Model):
    name = models.CharField(max_length=150)
    register_number = models.CharField(max_length=50, unique=True)
    email = models.EmailField(blank=True, null=True)
    password = models.CharField(max_length=128, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    can_create_games = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.register_number})"

class Game(models.Model):
    GAME_TYPES = [
        ('word_puzzle', 'Word Puzzle'),
        ('mcq', 'Multiple Choice Questions'),
        ('fill_blanks', 'Fill in the Blanks'),
        ('match_following', 'Match the Following'),
    ]

    title = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='games')
    game_type = models.CharField(max_length=20, choices=GAME_TYPES)
    instructions = models.TextField(help_text="How to play the game")
    explanation = models.TextField(help_text="The concept/explanation behind the answers")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='created_games')
    created_by_student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True, related_name='student_created_games')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=False, help_text="Designates whether students can see and play this game.")
    approval_status = models.CharField(max_length=20, choices=[('draft', 'Draft'), ('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='approved')
    rejection_reason = models.TextField(blank=True, null=True)
    clue1 = models.TextField(blank=True, null=True, help_text="First overall clue for match game")
    clue2 = models.TextField(blank=True, null=True, help_text="Second overall clue for match game")
    clue3 = models.TextField(blank=True, null=True, help_text="Third overall clue for match game")

    def __str__(self):
        return f"{self.title} ({self.get_game_type_display()})"

class WordPuzzleQuestion(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='word_puzzles')
    correct_word = models.CharField(max_length=100)
    letters_override = models.CharField(max_length=200, blank=True, null=True, help_text="Comma-separated custom letters to show (optional)")
    clue1 = models.TextField()
    clue1_time = models.IntegerField(default=15, help_text="Time in seconds for Clue 1 to appear")
    clue2 = models.TextField()
    clue2_time = models.IntegerField(default=30, help_text="Time in seconds for Clue 2 to appear")
    full_marks = models.IntegerField(default=10, help_text="Score before any clues appear")
    reduced_marks_clue1 = models.IntegerField(default=7, help_text="Score after Clue 1 appears")
    min_marks_clue2 = models.IntegerField(default=4, help_text="Score after Clue 2 appears")
    clue3 = models.TextField(blank=True, null=True, help_text="Third clue for word puzzle")

    def __str__(self):
        return self.correct_word

class MCQQuestion(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='mcq_questions')
    question_text = models.TextField()
    option_a = models.CharField(max_length=255)
    option_b = models.CharField(max_length=255)
    option_c = models.CharField(max_length=255)
    option_d = models.CharField(max_length=255)
    correct_option = models.CharField(max_length=1, choices=[('A', 'Option A'), ('B', 'Option B'), ('C', 'Option C'), ('D', 'Option D')])
    clue1 = models.TextField(blank=True, null=True, help_text="First clue for MCQ")
    clue2 = models.TextField(blank=True, null=True, help_text="Second clue for MCQ")
    clue3 = models.TextField(blank=True, null=True, help_text="Third clue for MCQ")

    def __str__(self):
        return self.question_text[:50]

class FillBlankQuestion(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='blank_questions')
    question_text = models.TextField(help_text="Use double underscores '__' to represent the blank. E.g. 'The capital of France is __.'")
    correct_answer = models.CharField(max_length=255)
    clue = models.TextField(blank=True, null=True, help_text="Optional clue for this question")
    clue1 = models.TextField(blank=True, null=True, help_text="First clue for fill in blanks")
    clue2 = models.TextField(blank=True, null=True, help_text="Second clue for fill in blanks")
    clue3 = models.TextField(blank=True, null=True, help_text="Third clue for fill in blanks")

    def __str__(self):
        return self.question_text[:50]

class MatchItem(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='match_items')
    left_item = models.CharField(max_length=255)
    right_item = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.left_item} -> {self.right_item}"

class GameAttempt(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attempts')
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='attempts')
    score = models.IntegerField()
    max_score = models.IntegerField()
    clues_used = models.IntegerField(default=0)
    completed_at = models.DateTimeField(auto_now_add=True)
    time_taken = models.IntegerField(help_text="Time taken in seconds")

    def __str__(self):
        return f"{self.student.name} - {self.game.title} - {self.score}/{self.max_score}"

    @property
    def is_blocked(self):
        attempts_count = GameAttempt.objects.filter(student=self.student, game=self.game).count()
        permission = StudentGamePlayPermission.objects.filter(student=self.student, game=self.game).first()
        allowed = permission.allowed_attempts if permission else 1
        return attempts_count >= allowed

class AnonymousFeedback(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_feedback')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"Feedback for {self.teacher.username} at {self.created_at}"

class StudentGamePlayPermission(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='play_permissions')
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='play_permissions')
    allowed_attempts = models.IntegerField(default=1, help_text="Number of attempts allowed for this student on this game")

    class Meta:
        unique_together = ('student', 'game')

    def __str__(self):
        return f"{self.student.name} - {self.game.title} (Allowed: {self.allowed_attempts})"

class PDFNote(models.Model):
    title = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='pdf_notes')
    description = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='notes/')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_notes')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.subject.name})"

class StudentMark(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='marks')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='student_marks')
    marks = models.IntegerField()
    max_marks = models.IntegerField(default=100)
    exam_type = models.CharField(max_length=50)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_marks')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'subject', 'exam_type')

    def __str__(self):
        return f"{self.student.name} - {self.subject.name} - {self.exam_type}: {self.marks}"

class TeacherSetting(models.Model):
    teacher = models.OneToOneField(User, on_delete=models.CASCADE, related_name='settings')
    anonymous_feedback_enabled = models.BooleanField(default=True, help_text="Allow students to submit anonymous suggestions.")
    replays_enabled = models.BooleanField(default=True, help_text="Allow students to replay completed games if unlocked.")
    games_enabled = models.BooleanField(default=True, help_text="Allow students to play games on the platform.")

    def __str__(self):
        return f"Settings for {self.teacher.username}"

class Announcement(models.Model):
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='announcements')

    def __str__(self):
        return f"Announcement on {self.created_at.strftime('%Y-%m-%d %H:%M')} by {self.created_by.username}"

class GameEntry(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='game_entries')
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='game_entries')
    entry_time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.name} entered {self.game.title} at {self.entry_time}"

