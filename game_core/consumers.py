import json
import threading
from channels.generic.websocket import JsonWebsocketConsumer
from asgiref.sync import async_to_sync
from django.db import close_old_connections
from .models import Student, User, FifaGameSession, FifaPlayer, FifaQuestion, FifaAnswerLog, FifaRound
from django.utils import timezone

class FifaConsumer(JsonWebsocketConsumer):
    def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.group_name = f"fifa_{self.session_id}"

        # Try to identify who is connecting
        self.user = self.scope.get('user')
        self.student_id = self.scope.get('session', {}).get('student_id')
        if self.student_id:
            try:
                self.student_id = int(self.student_id)
            except (ValueError, TypeError):
                pass

        # Check authorization
        self.is_host = False
        if self.user and self.user.is_authenticated:
            # Let's verify if this user is the host of the session
            try:
                session = FifaGameSession.objects.get(id=self.session_id)
                if session.host == self.user:
                    self.is_host = True
            except FifaGameSession.DoesNotExist:
                pass

        if not self.is_host and not self.student_id:
            self.close()
            return

        # Join room group
        async_to_sync(self.channel_layer.group_add)(
            self.group_name,
            self.channel_name
        )
        self.accept()

        # Send initial lobby state
        self.send_lobby_state()

    def disconnect(self, close_code):
        # Leave room group
        async_to_sync(self.channel_layer.group_discard)(
            self.group_name,
            self.channel_name
        )

    def receive_json(self, content):
        action = content.get('action')
        
        if action == 'join_game':
            self.handle_join_game(content)
        elif action == 'ready_status':
            self.handle_ready_status(content)
        elif action == 'start_game':
            self.handle_start_game()
        elif action == 'submit_answer':
            self.handle_submit_answer(content)
        elif action == 'timer_ended':
            self.handle_timer_ended(content)
        elif action == 'next_question':
            self.handle_next_question()

    def handle_join_game(self, data):
        if self.is_host:
            return  # Host doesn't join as a player

        group_name = data.get('group_name', '').strip()
        if not group_name:
            self.send_json({'error': 'Group Name is required.'})
            return

        try:
            student = Student.objects.get(id=self.student_id)
            session = FifaGameSession.objects.get(id=self.session_id)

            if session.status != 'waiting':
                self.send_json({'error': 'Game has already started or completed.'})
                return

            # Register student as player
            player, created = FifaPlayer.objects.get_or_create(
                session=session,
                student=student,
                defaults={'group_name': group_name}
            )
            if not created and player.group_name != group_name:
                player.group_name = group_name
                player.save()

            self.send_json({
                'type': 'join_success',
                'player_id': player.id,
                'group_name': player.group_name,
                'is_ready': player.is_ready
            })

            # Broadcast updated lobby to all
            self.broadcast_lobby_update()

        except Exception as e:
            self.send_json({'error': str(e)})

    def handle_ready_status(self, data):
        if self.is_host:
            return

        ready = data.get('ready', False)
        try:
            session = FifaGameSession.objects.get(id=self.session_id)
            player = FifaPlayer.objects.get(session=session, student_id=self.student_id)
            player.is_ready = ready
            player.save()

            # Broadcast update
            self.broadcast_lobby_update()
        except FifaPlayer.DoesNotExist:
            self.send_json({'error': 'Player not registered in session.'})

    def handle_start_game(self):
        if not self.is_host:
            self.send_json({'error': 'Only the host can start the game.'})
            return

        try:
            session = FifaGameSession.objects.get(id=self.session_id)
            if session.status != 'waiting':
                self.send_json({'error': 'Game already started.'})
                return

            # Count players and ready players
            players = session.players.all()
            if not players.exists():
                self.send_json({'error': 'No players have joined yet.'})
                return

            # Check if all players are ready
            ready_players = players.filter(is_ready=True)
            if ready_players.count() < players.count():
                # Let's allow starting anyway, or require all ready. Let's start anyway but log warning.
                pass

            session.status = 'playing'
            session.current_round = 1
            session.current_question_index = 0
            session.started_at = timezone.now()
            session.save()

            # Broadcast game start
            self.send_current_question()

        except Exception as e:
            self.send_json({'error': str(e)})

    def handle_submit_answer(self, data):
        if self.is_host:
            return

        question_id = data.get('question_id')
        selected_option = data.get('selected_option')  # A, B, C, D
        time_taken = data.get('time_taken', 0.0)

        try:
            session = FifaGameSession.objects.get(id=self.session_id)
            player = FifaPlayer.objects.get(session=session, student_id=self.student_id)
            question = FifaQuestion.objects.get(id=question_id, session=session)

            if session.status != 'playing':
                self.send_json({'error': 'Game is not in playing status.'})
                return

            # Check if already answered
            if FifaAnswerLog.objects.filter(player=player, question=question).exists():
                self.send_json({'error': 'Answer already submitted.'})
                return

            is_correct = (selected_option == question.correct_answer)

            # Apply negative marking logic:
            # Correct: flat points (we can use 10, or speed bonus. Let's do a base score of 10)
            # Incorrect: -2 points (negative marking)
            # Prevent double submission is handled by unique_together constraint in AnswerLog

            FifaAnswerLog.objects.create(
                player=player,
                question=question,
                selected_option=selected_option,
                is_correct=is_correct,
                time_taken=time_taken
            )

            # Inform this client that answer is locked
            self.send_json({
                'type': 'answer_locked',
                'question_id': question.id,
                'selected_option': selected_option,
                'is_correct': is_correct
            })

            # Broadcast answer submission event (to update host dashboard, list of who answered)
            async_to_sync(self.channel_layer.group_send)(
                self.group_name,
                {
                    'type': 'broadcast_player_submitted',
                    'player_id': player.id,
                    'player_name': player.student.name,
                    'group_name': player.group_name
                }
            )

            # Check if all players answered
            self.check_all_answered_and_trigger()

        except Exception as e:
            self.send_json({'error': str(e)})

    def handle_timer_ended(self, data):
        # Host or client sends timer_ended. We reveal answers to all
        if not self.is_host:
            # If a student client times out without submitting, auto-submit wrong
            question_id = data.get('question_id')
            try:
                session = FifaGameSession.objects.get(id=self.session_id)
                player = FifaPlayer.objects.get(session=session, student_id=self.student_id)
                question = FifaQuestion.objects.get(id=question_id, session=session)

                if not FifaAnswerLog.objects.filter(player=player, question=question).exists():
                    FifaAnswerLog.objects.create(
                        player=player,
                        question=question,
                        selected_option=None,
                        is_correct=False,
                        time_taken=float(session.question_timer)
                    )
                    self.send_json({
                        'type': 'answer_locked',
                        'question_id': question.id,
                        'selected_option': None,
                        'is_correct': False
                    })
                    
                    async_to_sync(self.channel_layer.group_send)(
                        self.group_name,
                        {
                            'type': 'broadcast_player_submitted',
                            'player_id': player.id,
                            'player_name': player.student.name,
                            'group_name': player.group_name
                        }
                    )
                    
                    self.check_all_answered_and_trigger()
            except Exception:
                pass
            return

        # If host sends it, we force reveal the question results
        self.reveal_question_results()

    def handle_next_question(self):
        if not self.is_host:
            return

        try:
            session = FifaGameSession.objects.get(id=self.session_id)
            total_q = session.questions.count()
            
            # Current question index is incremented
            next_idx = session.current_question_index + 1
            
            # Check if we just completed a round (every 5 questions)
            current_q_num = session.current_question_index + 1
            if current_q_num % 5 == 0:
                # We need to evaluate the round winner and trigger animation!
                self.evaluate_round_and_broadcast(session.current_round)
                # Increment round on the session
                session.current_round += 1
                session.current_question_index = next_idx
                session.save()
                return

            if next_idx >= total_q or next_idx >= session.total_questions:
                # Game is completed!
                self.complete_game(session)
            else:
                session.current_question_index = next_idx
                session.save()
                self.send_current_question()

        except Exception as e:
            self.send_json({'error': str(e)})

    def send_current_question(self):
        try:
            session = FifaGameSession.objects.get(id=self.session_id)
            question = session.questions.get(order=session.current_question_index)

            # Broadcast the question details and start timer
            async_to_sync(self.channel_layer.group_send)(
                self.group_name,
                {
                    'type': 'broadcast_question',
                    'question_index': session.current_question_index,
                    'question_id': question.id,
                    'question_text': question.question_text,
                    'option_a': question.option_a,
                    'option_b': question.option_b,
                    'option_c': question.option_c,
                    'option_d': question.option_d,
                    'timer_seconds': session.question_timer,
                    'timestamp': timezone.now().isoformat()
                }
            )
        except FifaQuestion.DoesNotExist:
            # Out of questions, complete the game
            session = FifaGameSession.objects.get(id=self.session_id)
            self.complete_game(session)

    def reveal_question_results(self):
        try:
            session = FifaGameSession.objects.get(id=self.session_id)
            question = session.questions.get(order=session.current_question_index)
            
            # Get list of correct and incorrect answers for this question
            logs = FifaAnswerLog.objects.filter(question=question)
            submissions = {}
            for log in logs:
                submissions[log.player.id] = {
                    'name': log.player.student.name,
                    'group': log.player.group_name,
                    'option': log.selected_option,
                    'is_correct': log.is_correct,
                    'time_taken': log.time_taken
                }

            async_to_sync(self.channel_layer.group_send)(
                self.group_name,
                {
                    'type': 'broadcast_reveal',
                    'question_id': question.id,
                    'correct_answer': question.correct_answer,
                    'submissions': submissions
                }
            )
        except Exception as e:
            self.send_json({'error': str(e)})

    def check_all_answered_and_trigger(self):
        try:
            session = FifaGameSession.objects.get(id=self.session_id)
            players = session.players.all()
            question = session.questions.get(order=session.current_question_index)
            
            logs_count = FifaAnswerLog.objects.filter(question=question).count()
            if logs_count >= players.count() and players.count() > 0:
                # Everyone has answered! Trigger reveal
                self.reveal_question_results()
        except Exception:
            pass

    def evaluate_round_and_broadcast(self, round_num):
        session = FifaGameSession.objects.get(id=self.session_id)
        
        # Questions in this round: indices (round_num-1)*questions_per_round to round_num*questions_per_round-1
        start_idx = (round_num - 1) * session.questions_per_round
        end_idx = round_num * session.questions_per_round
        questions = session.questions.filter(order__gte=start_idx, order__lt=end_idx)
        
        players = session.players.all()
        eligible_players = []
        all_players_results = {}

        for player in players:
            logs = FifaAnswerLog.objects.filter(player=player, question__in=questions)
            correct_count = logs.filter(is_correct=True).count()
            
            # Disqualified if they got any wrong option. 
            # Timeout (selected_option is None) counts as incorrect but let's treat it as:
            # If they got a wrong option (non-null and incorrect), that's definitely disqualified.
            # If they didn't answer (None), is it a wrong answer? Yes, incorrect.
            # To be eligible, they must have at least 3 correct, and 0 incorrect answers.
            # Wait, if incorrect counts both wrong options and timeouts, then a timeout will also disqualify them.
            # Let's count incorrect as ANY log with is_correct=False.
            incorrect_count = logs.filter(is_correct=False).count()
            
            total_score = 0
            total_time = 0.0
            for log in logs:
                if log.is_correct:
                    total_score += 10
                    total_time += log.time_taken
                else:
                    total_score -= 2 # Negative marking
            
            is_eligible = (correct_count == session.questions_per_round and incorrect_count == 0)
            
            all_players_results[player.id] = {
                'name': player.student.name,
                'group': player.group_name,
                'correct_count': correct_count,
                'incorrect_count': incorrect_count,
                'total_score': total_score,
                'total_time': total_time,
                'is_eligible': is_eligible,
                'wins': player.wins
            }

            if is_eligible:
                eligible_players.append({
                    'player': player,
                    'score': total_score,
                    'time': total_time
                })

        winner_player = None
        winner_id = None
        winner_group = None
        
        if eligible_players:
            # Sort: highest score, then fastest time
            eligible_players.sort(key=lambda x: (-x['score'], x['time']))
            winner_player = eligible_players[0]['player']
            winner_player.wins += 1
            winner_player.save()
            
            # Save Round Winner
            round_obj, _ = FifaRound.objects.get_or_create(
                session=session,
                round_number=round_num
            )
            round_obj.is_completed = True
            round_obj.winner = winner_player
            round_obj.save()
            
            winner_id = winner_player.id
            winner_group = winner_player.group_name
            # Update wins count in results dictionary
            all_players_results[winner_player.id]['wins'] = winner_player.wins

        # Broadcast round results and trigger FIFA animation
        async_to_sync(self.channel_layer.group_send)(
            self.group_name,
            {
                'type': 'broadcast_round_completed',
                'round_number': round_num,
                'winner_id': winner_id,
                'winner_name': winner_player.student.name if winner_player else "No Eligible Winner",
                'winner_group': winner_group,
                'players_results': all_players_results
            }
        )

    def complete_game(self, session):
        session.status = 'completed'
        session.save()
        
        # Determine the ultimate champion
        players = session.players.all()
        if players.exists():
            # Champion: most wins on the football field (most round wins).
            # Tie breaker: highest total score, then fastest total time across all logs
            player_stats = []
            for p in players:
                logs = FifaAnswerLog.objects.filter(player=p)
                total_score = sum(10 if log.is_correct else -2 for log in logs)
                total_time = sum(log.time_taken for log in logs if log.is_correct)
                player_stats.append({
                    'player': p,
                    'wins': p.wins,
                    'score': total_score,
                    'time': total_time
                })
            
            # Sort: wins desc, score desc, time asc
            player_stats.sort(key=lambda x: (-x['wins'], -x['score'], x['time']))
            champion = player_stats[0]['player']
            champion_name = champion.student.name
            champion_group = champion.group_name
        else:
            champion_name = "None"
            champion_group = "None"

        # Compile final visual standings results list
        players_results = []
        for p in players:
            players_results.append({
                'name': p.student.name,
                'group': p.group_name,
                'wins': p.wins
            })

        async_to_sync(self.channel_layer.group_send)(
            self.group_name,
            {
                'type': 'broadcast_game_completed',
                'champion_name': champion_name,
                'champion_group': champion_group,
                'players_results': players_results
            }
        )

    # Broadcast event handlers
    def broadcast_question(self, event):
        self.send_json(event)

    def broadcast_reveal(self, event):
        self.send_json(event)
        # Only the host consumer schedules the next action to avoid duplicate timers
        if self.is_host:
            timer = threading.Timer(4.0, self.auto_advance_background)
            timer.start()

    def broadcast_player_submitted(self, event):
        self.send_json(event)

    def broadcast_round_completed(self, event):
        self.send_json(event)

    def broadcast_game_completed(self, event):
        self.send_json(event)

    # Background Automated Transitions
    def auto_advance_background(self):
        close_old_connections()
        try:
            session = FifaGameSession.objects.get(id=self.session_id)
            total_q = session.questions.count()
            current_q_num = session.current_question_index + 1
            next_idx = session.current_question_index + 1
            
            # Check if this question ends a round
            if current_q_num % session.questions_per_round == 0:
                self.evaluate_round_and_broadcast(session.current_round)
                # Advance round state in session
                session.current_round += 1
                session.current_question_index = next_idx
                session.save()
                return

            if next_idx >= total_q or next_idx >= session.total_questions:
                self.complete_game(session)
            else:
                session.current_question_index = next_idx
                session.save()
                self.send_current_question()
        except Exception as e:
            print("Error in auto_advance_background:", e)

    def auto_next_question_background(self):
        close_old_connections()
        try:
            session = FifaGameSession.objects.get(id=self.session_id)
            total_q = session.questions.count()
            if session.current_question_index >= total_q or session.current_question_index >= session.total_questions:
                self.complete_game(session)
            else:
                self.send_current_question()
        except Exception as e:
            print("Error in auto_next_question_background:", e)

    def send_lobby_state(self):
        try:
            session = FifaGameSession.objects.get(id=self.session_id)
            players = session.players.all()
            players_list = [{
                'id': p.id,
                'name': p.student.name,
                'group_name': p.group_name,
                'is_ready': p.is_ready
            } for p in players]

            self.send_json({
                'type': 'lobby_state',
                'status': session.status,
                'players': players_list,
                'ready_count': players.filter(is_ready=True).count(),
                'total_count': players.count()
            })
        except Exception:
            pass

    def broadcast_lobby_update(self):
        try:
            session = FifaGameSession.objects.get(id=self.session_id)
            players = session.players.all()
            players_list = [{
                'id': p.id,
                'name': p.student.name,
                'group_name': p.group_name,
                'is_ready': p.is_ready
            } for p in players]

            async_to_sync(self.channel_layer.group_send)(
                self.group_name,
                {
                    'type': 'broadcast_lobby_state',
                    'status': session.status,
                    'players': players_list,
                    'ready_count': players.filter(is_ready=True).count(),
                    'total_count': players.count()
                }
            )
        except Exception:
            pass

    def broadcast_lobby_state(self, event):
        self.send_json(event)
