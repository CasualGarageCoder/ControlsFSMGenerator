class_name BaseCharacterController
extends Node

export(String) var descriptor_filename : String

# Sends the sequence readiness. When progress is 0, the sequence can be activated.
# Else, it indicates the progression of the cooldown for 1.0 to 0.0.
signal sequence_readiness(sequence, progress)

class IntermediateState:
	var state_name : String # State name
	var access : Array = [] # In fact, we don't care about if the controls has been pressed or not
	# because of the context.
	var access_name : Array = [] # Purely for debug purpose.
	var timer_reset : Array = [] # For each control move, a timer reset can occurs.
	var timeout_route : int # Timer timeout escape. No change in controls.
	var fire : Array = [] # Sequence Identifier. -1 if none.
        var freeze : bool

class ControlSequence:
	var duration : int = 0 # ms
	var cooldown : int = 0 # ms
	var infer : Array = [] # Triggering this sequence trigger onter cooldown timers ONLY.

onready var states : Array = [] # Array of IntermediateStates.

# Current state.
onready var current_state : int

# Timer timeout in ms.
onready var timer_timeout : Dictionary = {}

# Date at which the timer will expire. If -1, the timer is not in use.
onready var timer_expire : Dictionary = {}

# Sequence description for cooldown and duration.
onready var sequence : Array = []

# Maximum identifier for sequence timer.
onready var sequence_timer_max : int

# Current state of the controls. The derived scripts might use this to determine animations,
# movements and so on.
onready var current_control : Array = []

# Fake time. Fast alternative to OS calls.
onready var current_time : int = 0

# Keep starting state ID.
onready var starting_state : int

# Last control that was pressed. Can be 0 if a control as been released.
onready var last_pressed_control : int

# Timestamp of last control pressed.
onready var last_control_pressed : Array

# Timestamp of last control released.
onready var last_control_released : Array

# The character is "stuck" in an 'in_sequence' dead zone.
onready var in_sequence : bool = false

# Unshuffled controls.
onready var unshuffled_controls : Array

# Filterd controls.
onready var filtered_controls : Array

# If true, special movements aren't tracked (hence nor triggered).
onready var dampened : bool = false

## Initialisation. Read the JSON, collect and compute useful data.
func _ready():
	set_process(false)
	unshuffled_controls = [0]
	unshuffled_controls.append_array(range(1, GlobalControls.PLAYER_CONTROLS_DESCRIPTION.size() + 1))
	filtered_controls = unshuffled_controls
	var file = File.new()
	var err = file.open(descriptor_filename, File.READ)
	if err == OK:
		var text_content = file.get_as_text()
		var json_content = parse_json(text_content)
		# Let the fun begins.
		current_state = json_content["Start"]
		starting_state = current_state
		var control_count = json_content["ControlCount"]
		for _i in range(control_count + 1):
			current_control.append(false)
			last_control_pressed.append(-1)
			last_control_released.append(-1)
		var json_sequences : Array = json_content["Sequences"]
		var seq_count : int = json_sequences.size()
		for i in range(seq_count):
			var seq = json_sequences[i]
			var control_sequence : ControlSequence = ControlSequence.new()
			control_sequence.duration = seq["Duration"]
			control_sequence.cooldown = seq["Cooldown"]
			if "Infer" in seq:
				control_sequence.infer = seq["Infer"]
			sequence.append(control_sequence)
			var id_duration : int = i * 2
			var id_cooldown : int = id_duration + 1
			timer_timeout[id_duration] = control_sequence.duration
			timer_expire[id_duration] = -1
			timer_timeout[id_cooldown] = control_sequence.cooldown
			timer_expire[id_cooldown] = -1
		sequence_timer_max = seq_count * 2
		timer_timeout[sequence_timer_max] = json_content["SequenceTimeout"]
		timer_expire[sequence_timer_max] = -1
		var transitions : Array = json_content["Transitions"]
		for t in transitions:
			var state : IntermediateState = IntermediateState.new()
			for _i in range(control_count+1):
				state.access.append(0)
				state.access_name.append("")
				state.fire.append(-1)
				state.timer_reset.append([])
                                state.freeze = false
			for i in t:
				if "Name" in i:
					state.state_name = i["Name"]
					continue
				var target_id = i["Target"]
				if "Control" in i:
					state.access[i["Control"]] = target_id
					state.access_name[i["Control"]] = i["State"]
				if "Timeout" in i:
					# For now, we only consider the "SequenceTimer" timeout.
					state.timeout_route = target_id
				if "Fire" in i:
					state.fire[i["Control"]] = i["Fire"]
				if "Timer" in i:
					state.timer_reset[i["Control"]].append(seq_count * 2)
                                if "Freeze" in i:
                                        state.freeze = i["Freeze"]
			states.append(state)
	else:
		print("Unable to load file %s" % descriptor_filename)
		get_tree().quit(-1)
	set_process(true)

# Provide the number of sequences.
func get_sequence_count() -> int:
	return sequence.size()

# Reset the state machine.
func reset() -> void:
	set_process(false)
	current_state = starting_state
	for t in range(len(timer_expire)):
		if t < sequence_timer_max and t % 2 == 1:
			emit_signal("sequence_readiness", (t - 1) / 2, 0.0)
		timer_expire[t] = -1
	for t in range(len(current_control)):
		current_control[t] = false
		last_control_pressed[t] = -1
		last_control_pressed[t] = -1
	last_pressed_control = 0
	set_process(true)

# Entry point : Set the current control change.
func set_move(control : int, pressed : bool) -> void:
	var filtered_control : int = filter_control(control, pressed)
	var last_value : bool = current_control[filtered_control]
	current_control[filtered_control] = pressed
	if pressed:
		last_pressed_control = filtered_control
		last_control_pressed[filtered_control] = current_time
	else:
		last_pressed_control = 0
		last_control_released[filtered_control] = current_time

	if can_move() && (last_value != pressed):
		for timer in states[current_state].timer_reset[filtered_control]:
			timer_expire[timer] = current_time + timer_timeout[timer]
		var seq_id : int = states[current_state].fire[filtered_control]
		var override_sequence : bool = true
		if pressed and seq_id >= 0 and not dampened:
			timer_expire[sequence.size() * 2] = -1
			if timer_expire[(seq_id * 2) + 1] < 0: # If the timer is a cooldown, we don't activate special move.
				timer_expire[seq_id * 2] = current_time + sequence[seq_id].duration
				timer_expire[(seq_id * 2) + 1] = current_time + sequence[seq_id].cooldown
				override_sequence = activate_sequence(seq_id, sequence[seq_id].duration, sequence[seq_id].cooldown)
				invoke_decision_tree()
				# Other cooldown inference
				for i in sequence[seq_id].infer:
					var id : int = int((i * 2) + 1)
					var inf_id : int = int(i)
					timer_expire[id] = current_time + sequence[inf_id].cooldown
		in_sequence = false
		for i in range(sequence.size()):
			in_sequence = in_sequence or timer_expire[i * 2] > 0
		if override_sequence or (not in_sequence) or (not states[current_state].access[filtered_control].freeze):
			process_move(filtered_control, pressed)
		# Switch to next state.
		current_state = states[current_state].access[filtered_control]

# Is the character in dead-zone.
func is_in_sequence() -> bool:
	return in_sequence

# Processing function. Deal with the different timeouts.
# Uses delta to increment the current time. It's a quick alternative to OS calls.
func _process(delta : float):
	current_time += int(delta * 1000)
	for i in timer_expire.keys():
		if timer_expire[i] > 0:
			if i < sequence_timer_max and i % 2 == 1: # Cooldown timer.
				# Compute progression.
				var current : int = timer_expire[i]
				var timeout : int = timer_timeout[i]
				var progression : float = (timer_expire[i] - current_time) / float(timer_timeout[i])
				emit_signal("sequence_readiness", (i - 1) / 2, progression)
		if timer_expire[i] <= current_time and timer_expire[i] > 0:
			timer_expire[i] = -1
			on_timer_expire(i)
			if i == sequence_timer_max: #  Sequence breaker timeout.
				var next_state : int = states[current_state].timeout_route
				current_state = next_state
			elif i < sequence_timer_max:
				if i % 2 == 1: # Cooldown timer.
					emit_signal("sequence_readiness", (i - 1) / 2, 0.0)
				else:
					# Test in_sequence
					in_sequence = false
					for j in range(sequence.size()):
						in_sequence = in_sequence or timer_expire[j * 2] > 0
	delegate_process()

# Trigger a timer
func trigger_timer(timer : int, override : bool = false) -> bool:
	if current_time < timer_expire[timer] and !override:
		return false
	timer_expire[timer] = current_time + timer_timeout[timer]
	return true

# Force end timer.
func reset_timer(timer : int) -> void:
	timer_expire[timer] = -1
	on_timer_expire(timer)

# Unshuffle controls.
func restore_controls() -> void:
	if is_control_shuffle():
		filtered_controls = unshuffled_controls
		invoke_decision_tree()

# Shuffle controls
func shuffle_controls() -> void:
	if not is_control_shuffle():
		filtered_controls = [ 0 ]
		var ctr = range(1, GlobalControls.PLAYER_CONTROLS_DESCRIPTION.size() + 1)
		ctr.shuffle()
		filtered_controls.append_array(ctr)
		invoke_decision_tree()

func is_control_shuffle() -> bool:
	return unshuffled_controls != filtered_controls

# Invoked before effectively process the control. Can be used for simulation of 'confusion spell'.
func filter_control(control : int, _pressed : int) -> int:
	return filtered_controls[control]

# Set the dampening flag.
func block_special_moves(var flag : bool) -> void:
	dampened = flag

## "Virtual Methods"

# Invoked when the decision tree needs to be evaluated.
func invoke_decision_tree() -> void:
	pass

# Invoked when a sequence has been completed.
# sequence_id is the identifier of the sequence (which value matches a constant generated in the
#   singleton.
# duration and cooldown are provided for information only. The duration "dead zone" and the
#   cooldown timer are already managed.
func activate_sequence(_sequence_id : int, _duration : int, _cooldown : int) -> bool:
	return false

# Invoked when a control can be processed (i.e. not in a sequence dead zone).
#   Can be used for trigerring an attack, a jump or any kind in instant move.
func process_move(_control : int, _pressed : bool) -> void:
	pass

# Invoked whenever a timer expires. The timer identifier matches constants generated
#   in the associated singleton.
func on_timer_expire(_timer : int) -> void:
	pass

# Invoked to determine if a control change can be processed. Can be used to simulate stun or
#   other kind of behavior modifier.
func can_move() -> bool:
	return true

# Allow performing extra processing.
func delegate_process() -> void:
	pass

# Activate an effect.
func activate_effect(_scene : Node, _pos : Vector2) -> void:
	pass

# Effect finished.
func effect_finished(_scene : Node) -> void:
	pass
