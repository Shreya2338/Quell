# Quell
A smart tremor-monitoring platform connecting wearable therapy, real-time insights, and collaborative Parkinson’s care. We're not just tracking, we're treating.

#  🏥 The Background
Over 10 million people worldwide are diagnosed with Parkinson's, 80% of which suffer from severe, daily motor complications as oral medications inevitably fail to maintain a steady therapeutic window as neurodegeneration advances. 

As the brain loses its ability to store daily Parkinson's medicines (such as Levodopa), the efficacy of patients' treatments : falling levels cause premature wear-off with severe tremors and fall-inducing motor freezes, while spiking levels trigger dyskinesia (uncontrollable, chaotic body jerking).

Relying on fixed schedules and paper diaries leaves doctors blind to medication wear-off, trapping patients in hours of shaking and freezing while caregivers react only after a fall.


# ⛑️ Our Solution - Quelling the Pain
After researching the biological breakdown of Parkinson’s, we realized that traditional devices act as digital bystanders, simply counting tremors while patients remain trapped between exhausting shaking and sudden motor freezing. 
Quell closes that loop with three critical interventions:
1. Active Relief at the Fingertips 
Applying Prof. Peter Tass’s [patented research on vibrotactile stimulation] (https://pmc.ncbi.nlm.nih.gov/articles/PMC8771098/), the wristband delivers targeted fingertip micro-pulses that disrupt chaotic brain signals and quell tremors in real time, reducing the harsh symptoms that patients suffer from in their day-to-day lives. 

2. Smarter Medication Windows
As dopamine storage degrades, rigid medication schedules fail to prevent wearing-off tremors and peak-dose dyskinesia. 
Quell maps tremors against dose timestamps to suggest an optimized medicine ingestion schedule in the form of a medical report available to the patient's clinician/doctor, eliminating likely untreated off-state gaps under the supervision of your personal healthcare provider.

3. Early Warning Alerts Preventing Emergencies
Rather than waiting for the emergency or injury to occur, Quell focuses on prevention. 
Quell catches rising tremor patterns 20 to 45 minutes before full motor freezing sets in and immediately dispatches an explainable alert to caregivers and nurses: telling them not just that risk is present, but exactly why 
>*Dose overdue by 25 min; resting tremor rising, high fall risk on next transfer* 

Caregivers can step in to assist with walking and administer care before an accident ever happens.

# 📚 The Scientific Framework
## Vibrotactile Coordinated Reset (vCR)
- **The Clinical Problem**: As Parkinson's progresses, basal ganglia circuits become abnormally synchronized, driving 4–6 Hz resting tremors. Monotonous vibration causes rapid sensory adaptation and central habituation within seconds.

- **The Mechanism**: Following Prof. Peter Tass’s research, high-frequency 250 Hz micro-bursts in a 3:2 on-off ratio pattern stimulate rapidly adapting cutaneous mechanoreceptors (Pacinian corpuscles) on median and radial nerves to act as a non-invasive sensory gate that disrupts hyper-synchronized oscillatory loops.

- **The Burst Pattern & Closed-Loop Control**: Uses an ~834ms macro cycle consisting of 3 active pulse cycles ~500ms followed by 2 silent pause cycles. Re-evaluates tremor power every 20–30 seconds; if 4–6 Hz power drops by >%50, the motor halts, with a strict 180-second safety cutoff to prevent nerve adaptation and overheating.

## Our Hardware
- **ESP32-S3-Zero (Microcontroller)**: Acts as the central hub, polling sensor data at a rapid 200Hz. It streams these live readings over Wi-Fi and uses the same Wi-Fi protocol to receive real-time commands that trigger the haptic motor.

- **MPU 6050 (IMU)**: A 6-axis sensor (accelerometer and gyroscope) connected via I2C. Polled at 200Hz, it captures the raw spatial kinematics needed to isolate the exact 4–6 Hz frequency signature of Parkinsonian resting tremors.

- **DRV2605L (Haptic Driver) + ERM Vibration Motor**: Interfaced via I2C. Upon receiving Wi-Fi commands through the ESP32, this precision driver triggers the targeted 250 Hz micro-bursts in a 3:2 on-off ratio pattern and manages the ~834ms vCR therapy cycles to safely disrupt hyper-synchronized brain signals.

## Edge Data Processing Pipeline
- **Magnitude Reduction**: Squashes 6 raw IMU channels (a_x, a_y, a_z, and roll, pitch, yaw) into 2 orientation-independent scalars via Euclidean norms to fit ESP32 RAM.

- **4th-Order Butterworth Filter (3.5–7.5 Hz)**: Uses a 4th-order IIR difference equation evaluated point-by-point to strip gravity offsets (0 Hz) and high-frequency noise.

- **Sliding Buffer (50% Overlap)**: Collects a 256-sample window (2.56s) and hops forward by 128 samples (1.28s) for low-latency tremor tracking.

- **Hanning-Windowed Real FFT**: Tapers boundaries to eliminate spectral leakage and computes frequency spectra.

# ⛰️ Challenges We Ran Into
- **Translating Complex Biomedical Signals into Simple Visuals**: Designing a unified dashboard that remains simple and accessible for senior patients while providing clinical depth for healthcare providers, alongside researching signal-processing algorithms to clean raw motion data and differentiate tremors from dyskinesia.

- **Taming High-Frequency Sensor Streams**: Engineering a database schema capable of capturing and querying continuous time-series motion data alongside discrete, user-logged medication schedules without hitting performance bottlenecks.

- **Deciphering Low-Level Hardware Protocols**: Navigating hardware specs, registers, and I2C communication protocols to reliably read sensor data from the MPU-6050 and control actuators via the ESP32-S3.

- **Striking a Balance Between Durability and Modularity**: Engineering a wristband prototype robust enough to wear, yet modular enough to expose pinouts for quick hardware swaps—a lifesaver when we fried a couple of microcontrollers mid-build!

- **Wrestling with SMTP and Secure Messaging Protocols**: Navigating backend email service configurations and authentication workflows to deliver reliable automated notifications and clinician summaries.

# 🏆 What We're Proud Of
- **End-to-End Integrated Ecosystem**: Built a complete, functional hardware-to-cloud pipeline—from low-level telemetry capture on an ESP32-S3 wristband to real-time database logging and interactive data visualization.

- **Closed-Loop Vibrotactile Therapy**: Successfully implemented localized haptic feedback using a dedicated haptic driver and motor, enabling targeted sensory stimulation upon tremor detection.

- **Intelligent Medication & Symptom Tracking**: Designed a system that correlates real-time tremor trends with user medication schedules, laying the foundation for data-driven dose optimization and automated clinical report generation.

- **User-Centered UI/UX**: Crafted high-fidelity, highly accessible patient and clinician interface prototypes in Figma, prioritizing readability and high-contrast visuals tailored for senior users.

# 📜 What We Learned
- **Hardware-Software Synergy**: Integrating embedded firmware (ESP32-S3, MPU-6050, haptic drivers) with a cloud backend gave us a much deeper appreciation for full-stack IoT architecture—especially managing hardware timing, signal noise, and data transmission payloads.

- **Designing for Accessibility**: Developing interfaces for senior users and clinicians taught us the importance of clear data hierarchy, high contrast, and simple user flows. Designing in Figma made it clear that accessibility isn't just a design choice, but a core functional requirement.

- **Biomedical Signal Processing**: We gained valuable hands-on experience researching clinical literature to understand how inertial sensor data correlates with neurological symptoms like rest tremors and dyskinesia, and how to preprocess raw motion data effectively.

- **Hardware Iteration & Resilience**: Working with physical components taught us how critical modular physical design and prototyping are—especially when debugging fried components and iterating on wearable ergonomics!

#  🎯 What's Next?
- **Multi-Finger Vibrotactile Actuation**: Expand our haptic therapy mechanism beyond single-point stimulation to incorporate individually controlled vibrotactile actuators across multiple fingers for targeted suppression.
