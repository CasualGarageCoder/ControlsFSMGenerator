extends Node

export(String) var descriptor_filename : String

class IntermediateState:
	var state_name : String # State name
	
	var access : Array = [] # In fact, we don't care about if the controls has been pressed or not
	# because of the context.
	
	var access_name : Array = [] # Purely for debug purpose.
	
	var timer_reset : Array = [] # For each control move, a timer reset can occurs.
	
	var timeout_route : int # Timer timeout escape. No change in controls.
	
	var fire : Array = [] # Sequence Identifier. -1 if none.

class ControlSequence:
	var duration : int # ms
	var cooldown : int # ms
	
	func _to_string():
		print("Duration %dms, Cooldown %sms" % [duration, cooldown])

onready var states : Array = [] # Array of IntermediateStates.

onready var current_state : int

onready var control_count : int

onready var timer_timeout : Array = []

onready var timer_expire : Array = []

onready var sequence : Array = []

onready var current_control : Array = []

onready var current_time : int = 0

func _ready():
	var file = File.new()
	var err = file.open(descriptor_filename, File.READ)
	if err == OK:
		var text_content = file.get_as_text()
		var json_content = parse_json(text_content)
		# Let the fun begins.
		current_state = json_content["Start"]
		control_count = json_content["ControlCount"]
		for _i in range(control_count):
			current_control.append(false)
		var json_sequences : Array = json_content["Sequences"]
		var seq_count : int = json_sequences.size()
		for i in range(seq_count):
			var seq = json_sequences[i]
			var control_sequence : ControlSequence = ControlSequence.new()
			control_sequence.duration = seq["Duration"]
			control_sequence.cooldown = seq["Cooldown"]
			sequence.append(control_sequence)
			timer_timeout.append(control_sequence.duration)
			timer_expire.append(-1)
			timer_timeout.append(control_sequence.cooldown)
			timer_expire.append(-1)
		timer_timeout.append(json_content["SequenceTimeout"])
		timer_expire.append(-1)
		var transitions : Array = json_content["Transitions"]
		for t in transitions:
			var state : IntermediateState = IntermediateState.new()
			for _i in range(control_count):
				state.access.append(0)
				state.access_name.append("")
				state.fire.append(-1)
				state.timer_reset.append([])
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
			states.append(state)
	set_process(true)
	set_process_input(true)

# Entry point : Set the current control change.
func set_move(control : int, pressed : bool) -> void:
	print("---- Entry state %d (%s) ----" % [current_state, states[current_state].state_name])
	print("Set move %d = %s" % [control, pressed])
	var filtered_control : int = filter_control(control, pressed)
	current_control[filtered_control] = pressed
	print(current_control)
	for timer in states[current_state].timer_reset[filtered_control]:
		timer_expire[timer] = current_time + timer_timeout[timer]
	var seq_id : int = states[current_state].fire[filtered_control]
	var override_sequence : bool = true
	if pressed and seq_id >= 0:
		print("Try to activate sequence %d (out of %d)" % [seq_id, sequence.size()])
		timer_expire[sequence.size() * 2] = -1
		if timer_expire[(seq_id * 2) + 1] < 0: # If the timer is a cooldown, we don't activate special move.
			timer_expire[seq_id * 2] = current_time + sequence[seq_id].duration
			timer_expire[(seq_id * 2) + 1] = current_time + sequence[seq_id].cooldown
			override_sequence = activate_sequence(seq_id, sequence[seq_id].duration, sequence[seq_id].cooldown)
		else:
			print("Cooldown still active for sequence %d" % seq_id)

	# Determine if we are in a sequence "dead zone".
	var in_sequence : bool = false
	for i in range(sequence.size()):
		in_sequence = in_sequence || timer_expire[i * 2] > 0

	if in_sequence:
		print("Still in at least one sequence 'dead zone'")

	if can_move() and override_sequence and not in_sequence:
		process_move(filtered_control, pressed)

	# Switch to next state.
	var target_name = states[current_state].access_name[filtered_control]
	current_state = states[current_state].access[filtered_control]
	print("---- Exit state %d (%s / %s) ----" % [current_state, states[current_state].state_name, target_name])

func _process(delta : float):
	current_time += int(delta * 1000)
	for i in range(timer_expire.size()):
		if timer_expire[i] < 0:
			continue
		if timer_expire[i] <= current_time:
			timer_expire[i] = -1
			on_timer_expire(i)
			if i == (timer_expire.size() - 1):
				var next_state : int = states[current_state].timeout_route
				current_state = next_state
				print("---- Timeout to state %d (%s) ----" % [current_state, states[current_state].state_name])


## "Virtual Methods"

func activate_sequence(sequence_id : int, _duration : int, _cooldown : int) -> bool:
	print("Activate sequence %d" % sequence_id)
	return false

func process_move(control : int, pressed : bool) -> void:
	print("Process move %d = %s" % [control, pressed])

func on_timer_expire(timer : int) -> void:
	print("Timer %s has expired" % timer)

func filter_control(control : int, _pressed : int) -> int:
	return control

func can_move() -> bool:
	return true

## Debug

func _input(event):
	## Debug specific to four controls as defined in the example rules file.
	if event.is_action_pressed("ui_down") && (!event.is_echo()):
		set_move(3, true)
	if event.is_action_pressed("ui_up") && (!event.is_echo()):
		set_move(2, true)
	if event.is_action_pressed("ui_right") && (!event.is_echo()):
		set_move(1, true)
	if event.is_action_pressed("ui_left") && (!event.is_echo()):
		set_move(0, true)

	if event.is_action_released("ui_down") && (!event.is_echo()):
		set_move(3, false)
	if event.is_action_released("ui_up") && (!event.is_echo()):
		set_move(2, false)
	if event.is_action_released("ui_right") && (!event.is_echo()):
		set_move(1, false)
	if event.is_action_released("ui_left") && (!event.is_echo()):
		set_move(0, false)
