import 'package:flutter/material.dart';
import '../services/api_service.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});
  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {

  final username = TextEditingController();
  final email = TextEditingController();
  final password = TextEditingController();
  final location = TextEditingController();

  registerUser() async {
    final response = await ApiService.register({
      "username": username.text,
      "email": email.text,
      "password": password.text,
      "location": location.text,
    });

    if (response["access"] != null) {
      Navigator.pushReplacementNamed(context, "/home");
    } else {
      print(response["error"]);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Padding(
        padding: EdgeInsets.all(20),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [

            Text("Register", style: TextStyle(fontSize: 30)),

            TextField(controller: username, decoration: InputDecoration(labelText: "Username")),
            TextField(controller: email, decoration: InputDecoration(labelText: "Email")),
            TextField(controller: password, decoration: InputDecoration(labelText: "Password")),
            TextField(controller: location, decoration: InputDecoration(labelText: "Location")),

            SizedBox(height: 20),

            ElevatedButton(
              onPressed: registerUser,
              child: Text("Create Account"),
            )
          ],
        ),
      ),
    );
  }
}