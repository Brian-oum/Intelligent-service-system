import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  static const baseUrl = "http://192.168.100.38:8000/api";

  // REGISTER
  static Future register(data) async {
    final response = await http.post(
      Uri.parse("$baseUrl/auth/register/"),
      body: data,
    );

    return jsonDecode(response.body);
  }

  // LOGIN
  static Future login(data) async {
    final response = await http.post(
      Uri.parse("$baseUrl/auth/login/"),
      body: data,
    );

    return jsonDecode(response.body);
  }
}