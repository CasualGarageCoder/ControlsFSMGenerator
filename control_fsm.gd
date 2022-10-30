class_name BaseCharacterController
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

onready var states : Array = [] # Array of IntermediateStates.

# Current state.
onready var current_state : int

# Timer timeout in ms.
onready var timer_timeout : Array = []

# Date at which the timer will expire. If -1, the timer is not in use.
onready var timer_expire : Array = []

# Sequence description for cooldown and duration.
onready var sequence : Array = []

# Current state of the controls. The derived scripts might use this to determine animations,
# movements and so on.
onready var current_control : Array = []

# Fake time. Fast alternative to OS calls.
onready var current_time : int = 0

## Initialisation. Read the JSON, collect and compute useful data.
func _ready():
        var file = File.new()
        var err = file.open(descriptor_filename, File.READ)
        if err == OK:
                var text_content = file.get_as_text()
                var json_content = parse_json(text_content)
                # Let the fun begins.
                current_state = json_content["Start"]
                var control_count = json_content["ControlCount"]
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
        var filtered_control : int = filter_control(control, pressed)
        current_control[filtered_control] = pressed
        if can_move():
                for timer in states[current_state].timer_reset[filtered_control]:
                        timer_expire[timer] = current_time + timer_timeout[timer]
                var seq_id : int = states[current_state].fire[filtered_control]
                var override_sequence : bool = true
                if pressed and seq_id >= 0:
                        timer_expire[sequence.size() * 2] = -1
                        if timer_expire[(seq_id * 2) + 1] < 0: # If the timer is a cooldown, we don't activate special move.
                                timer_expire[seq_id * 2] = current_time + sequence[seq_id].duration
                                timer_expire[(seq_id * 2) + 1] = current_time + sequence[seq_id].cooldown
                                override_sequence = activate_sequence(seq_id, sequence[seq_id].duration, sequence[seq_id].cooldown)

                # Determine if we are in a sequence "dead zone".
                var in_sequence : bool = false
                for i in range(sequence.size()):
                        in_sequence = in_sequence || timer_expire[i * 2] > 0

                if override_sequence and not in_sequence:
                        process_move(filtered_control, pressed)

        # Switch to next state.
        current_state = states[current_state].access[filtered_control]

# Processing function. Deal with the different timeouts.
# Uses delta to increment the current time. It's a quick alternative to OS calls.
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
        delegate_process()

# Trigger a timer
func trigger_timer(timer : int) -> bool:
        if current_time < timer_expire[timer]:
                return false
        timer_expire[timer] = current_time + timer_timeout[timer]
        return true

## "Virtual Methods"

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

# Invoked before effectively process the control. Can be used for simulation of 'confusion spell'.
func filter_control(control : int, _pressed : int) -> int:
        return control

# Invoked to determine if a control change can be processed. Can be used to simulate stun or
#   other kind of behavior modifier.
func can_move() -> bool:
        return true

# Allow performing extra processing.
func delegate_process() -> void:
        pass
