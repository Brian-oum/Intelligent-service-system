import 'package:flutter/material.dart';
import '../services/api_service.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _formKey = GlobalKey<FormState>();
  
  final username = TextEditingController();
  final email = TextEditingController();
  final password = TextEditingController();
  final location = TextEditingController();
  
  bool _isLoading = false;

  Future<void> registerUser() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
    });

    try {
      // Matching exactly what your Django backend 'request.POST' parameters expect
      final response = await ApiService.register({
        "username": username.text.trim(),
        "email": email.text.trim(),
        "password": password.text,
        "location": location.text.trim(),
      });

      // Adjust this condition to match your Django REST API response tokens
      if (response["access"] != null || response["success"] == true) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text("Account created successfully. Please log in.")),
          );
          Navigator.pushReplacementNamed(context, "/home");
        }
      } else {
        _showErrorSnackBar(response["error"] ?? "Registration failed.");
      }
    } catch (e, stackTrace) {
      print("REGISTER ERROR: $e");
      print(stackTrace);
      _showErrorSnackBar(e.toString());
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  void _showErrorSnackBar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Colors.redAccent,
      ),
    );
  }

  @override
  void dispose() {
    username.dispose();
    email.dispose();
    password.dispose();
    location.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF9FAFB), // Matching web registration-wrapper background
      body: Center(
        child: SingleChildScrollView(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 20.0),
            child: Container(
              padding: const EdgeInsets.all(32.0),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(24.0),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.04),
                    blurRadius: 20,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Form(
                key: _formKey,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Web Component: .reg-header
                    Container(
                      padding: const EdgeInsets.only(bottom: 4),
                      decoration: const BoxDecoration(
                        border: Border(
                          bottom: BorderSide(color: Colors.black, width: 3.0),
                        ),
                      ),
                      child: const Text(
                        "Need a Service...",
                        style: TextStyle(
                          fontSize: 24,
                          fontWeight: FontWeight.w600,
                          color: Color(0xFF374151),
                        ),
                      ),
                    ),
                    const SizedBox(height: 32),

                    // Username Input Field
                    _buildFormLabel("Username"),
                    TextFormField(
                      controller: username,
                      decoration: _buildPillInputDecoration("Enter username"),
                      validator: (v) => v!.isEmpty ? "Username is required" : null,
                    ),
                    const SizedBox(height: 18),

                    // Email Input Field
                    _buildFormLabel("Email Address"),
                    TextFormField(
                      controller: email,
                      keyboardType: TextInputType.emailAddress,
                      decoration: _buildPillInputDecoration("email@example.com"),
                      validator: (v) => v!.isEmpty ? "Email is required" : null,
                    ),
                    const SizedBox(height: 18),

                    // Location Field
                    _buildFormLabel("Your Location"),
                    TextFormField(
                      controller: location,
                      readOnly: true, // Emulating the web map modal trigger element
                      decoration: _buildPillInputDecoration(
                        "📍 Tap to pin your area",
                        isMapTrigger: true,
                      ),
                      onTap: () {
                        // TODO: Open your Leaflet mobile alternative view or Google Maps picker
                        // For prototyping placeholder assignment:
                        location.text = "Nairobi, Kenya"; 
                      },
                      validator: (v) => v!.isEmpty ? "Location mapping is required" : null,
                    ),
                    const SizedBox(height: 18),

                    // Password Input Field
                    _buildFormLabel("Password"),
                    TextFormField(
                      controller: password,
                      obscureText: true,
                      decoration: _buildPillInputDecoration("••••••••"),
                      validator: (v) => v!.length < 6 ? "Password is too short" : null,
                    ),
                    const SizedBox(height: 32),

                    // Primary Action Button (Web Component: .btn-register)
                    SizedBox(
                      width: double.infinity,
                      height: 54,
                      child: ElevatedButton(
                        onPressed: _isLoading ? null : registerUser,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF000000),
                          foregroundColor: Colors.white,
                          disabledBackgroundColor: Colors.grey,
                          elevation: 0,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(50),
                          ),
                        ),
                        child: _isLoading
                            ? const SizedBox(
                                height: 20,
                                width: 20,
                                child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                              )
                            : const Text(
                                "Create Account",
                                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                              ),
                      ),
                    ),
                    
                    const SizedBox(height: 20),
                    
                    // Back Link Navigation
                    Center(
                      child: TextButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text(
                          "← Back to Login",
                          style: TextStyle(color: Colors.black54, fontSize: 14),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  // Component Building Helper: Custom Field Labels
  Widget _buildFormLabel(String labelText) {
    return Padding(
      padding: const EdgeInsets.only(left: 14.0, bottom: 8.0),
      child: Text(
        labelText,
        style: const TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
          color: Color(0xFF374151),
        ),
      ),
    );
  }

  // UI Construction Style: Replicates .form-control-pill
  InputDecoration _buildPillInputDecoration(String hint, {bool isMapTrigger = false}) {
    return InputDecoration(
      hintText: hint,
      hintStyle: TextStyle(color: Colors.grey.shade400, fontSize: 14),
      filled: true,
      fillColor: isMapTrigger ? const Color(0xFFF9FAFB) : Colors.white,
      contentPadding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(50),
        borderSide: BorderSide(
          color: const Color(0xFFD1D5DB),
          style: isMapTrigger ? BorderStyle.solid : BorderStyle.solid,
        ),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(50),
        borderSide: const BorderSide(color: Colors.black, width: 1.5),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(50),
        borderSide: const BorderSide(color: Colors.redAccent),
      ),
      focusedErrorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(50),
        borderSide: const BorderSide(color: Colors.redAccent, width: 1.5),
      ),
    );
  }
}