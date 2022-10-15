extends Node

export(String) var descriptor_filename : String

class IntermediateState:
	var access : Array = [] # In fact, we don't care about if the controls has been pressed or not
	# because of the context.
	var timer_reset : Array = [] # For each control move, a timer reset can occurs.
	
	var timeout_route : Dictionary = {} # Timer timeout escape. No change in controls.
	
	var fire : Array = [] # Sequence Identifier. -1 if none.

class ControlSequence:
	var duration : int # ms
	var cooldown : int # ms

onready var states : Array = [] # Array of IntermediateStates.

onready var current_state : int

onready var control_count : int

onready var timer_timeout : Dictionary = {}

onready var timer_expire : Dictionary = {}

onready var sequence : Array = []

onready var current_control : Array = []

func _ready():
	var file = File.new()
	var err = file.open(descriptor_filename, File.READ)
	if err == OK:
		var text_content = file.get_as_text()
		var json_content = parse_json(text_content)
		# Let the fun begins.
		current_state = json_content["Start"]
		control_count = json_content["ControlCount"]
		for i in range(control_count):
			current_control.append(false)
		timer_timeout["SequenceTimer"] = json_content["SequenceTimeout"]
		for i in json_content["Sequences"]:
			var control_sequence : ControlSequence = ControlSequence.new()
			control_sequence.duration = i["Duration"]
			control_sequence.cooldown = i["Cooldown"]
			sequence.append(control_sequence)
		var transitions : Array = json_content["Transitions"]
		for t in transitions:
			var state : IntermediateState = IntermediateState.new()
			for i in range(control_count):
				state.access.append(0)
				state.fire.append(-1)
			for i in t:
				var target_id = i["Target"]
				if "Control" in i:
					state.access[i["Control"]] = target_id
				if "Timeout" in i:
					# For now, we only consider the "SequenceTimer" timeout.
					state.timeout_route[i["Timeout"]] = target_id
				if "Fire" in i:
					state.fire[i["Control"]] = i["Fire"]
				if "Timer" in i:
					state.timer_reset[i["Control"]].append(i["Timer"])
			states.append(state)
	set_process(true)

# Entry point : Set the current control change.
func set_move(control : int, pressed : bool) -> void:
	# TODO Filter
	current_control[control] = pressed
	for timer in states[current_state].timer_reset:
		var current_time : int = OS.get_current_msec()
		timer_expire[timer] = current_time + timer_timeout[timer]
	var seq_id : int = states[current_state].fire[control]
	var override_sequence : bool = true
	if pressed and seq_id >= 0:
		override_sequence = activate_sequence(seq_id, sequence[seq_id].delay, sequence[seq_id].cooldown)

	if override_sequence:
		process_move(control, pressed)

	current_state = states[current_state].access[current_state]

func _process(_delta : float):
	var current_time : int = OS.get_current_msec()
	for i in timer_expire:
		if timer_expire[i] < 0:
			continue
		if timer_expire[i] <= current_time:
			timer_expire[i] = -1
		if i in states[current_state].timeout_route:
			var next_state : int = states[current_state].timeout_route[i]
			on_timer_expire(i)
			current_state = next_state

## "Virtual Methods"

func activate_sequence(_sequence_id : int, _delay : int, _cooldown : int) -> bool:
	return false

func process_move(_control : int, _pressed : bool) -> void:
	pass

func on_timer_expire(timer : String) -> void:
	pass
