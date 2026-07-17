import 'package:flutter/material.dart';

class WelcomePage extends StatefulWidget {
  const WelcomePage({Key? super.key});

  @override
  State<WelcomePage> createState() => _WelcomePageState();
}

class _WelcomePageState extends State<WelcomePage> {
  bool _animate = false;

  @override
  void initState() {
    super.initState();
    // Triggers the animation shortly after the page loads
    Future.delayed(const Duration(milliseconds: 300), () {
      setState(() {
        _animate = true;
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    final Size screenSize = MediaQuery.of(context).size;

    return Scaffold(
      body: Stack(
        children: [
          // 1. Clear, Premium Gradient Background
          Container(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  Color(0xFFF8FAFC), // Ultra-light slate
                  Color(0xFFE2E8F0), // Soft premium grey
                ],
              ),
            ),
          ),

          // Decorative subtle background blur circles for a modern UI look
          Positioned(
            top: -screenSize.height * 0.1,
            right: -screenSize.width * 0.2,
            child: Container(
              width: screenSize.width * 0.8,
              height: screenSize.width * 0.8,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: const Color(0xFF3B82F6).withOpacity(0.04), // Soft blue tint
              ),
            ),
          ),

          // 2. Main Content Layout
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Spacer(flex: 2),

                  // 3. Animated Header / Brand Icon
                  AnimatedAnimatedOpacityAndSlide(
                    animate: _animate,
                    delayMs: 0,
                    child: Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(20),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withOpacity(0.04),
                            blurRadius: 20,
                            offset: const Offset(0, 10),
                          ),
                        ],
                      ),
                      child: const Icon(
                        Icons.home_repair_service_rounded,
                        size: 48,
                        color: Color(0xFF1E3A8A), // Deep Premium Navy
                      ),
                    ),
                  ),
                  const SizedBox(height: 32),

                  // 4. Animated Typography (Title)
                  AnimatedAnimatedOpacityAndSlide(
                    animate: _animate,
                    delayMs: 200,
                    child: RichText(
                      text: const TextSpan(
                        style: TextStyle(
                          fontSize: 40,
                          fontWeight: FontWeight.bold,
                          height: 1.2,
                          color: Color(0xFF0F172A), // Dark Slate
                        ),
                        children: [
                          TextSpan(text: 'Your Home.\n'),
                          TextSpan(
                            text: 'Perfected.',
                            style: TextStyle(
                              color: Color(0xFF2563EB), // Vibrant Accent Blue
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Animated Subtitle
                  AnimatedAnimatedOpacityAndSlide(
                    animate: _animate,
                    delayMs: 400,
                    child: Text(
                      'From seamless cleaning to expert electrical repairs. Professional homestead care, handled with absolute precision.',
                      style: TextStyle(
                        fontSize: 16,
                        color: Colors.black.withOpacity(0.6),
                        height: 1.5,
                      ),
                    ),
                  ),

                  const Spacer(flex: 3),

                  // 5. Interactive Service Micro-Cards (Quick Preview)
                  AnimatedAnimatedOpacityAndSlide(
                    animate: _animate,
                    delayMs: 600,
                    child: Row(
                      children: [
                        _buildServiceBadge(Icons.cleaning_services_rounded, 'Cleaning'),
                        const SizedBox(width: 12),
                        _buildServiceBadge(Icons.electrical_services_rounded, 'Electrical'),
                        const SizedBox(width: 12),
                        _buildServiceBadge(Icons.build_circle_rounded, 'Repairs'),
                      ],
                    ),
                  ),
                  const SizedBox(height: 40),

                  // 6. Premium Call to Action Button
                  AnimatedAnimatedOpacityAndSlide(
                    animate: _animate,
                    delayMs: 800,
                    child: SizedBox(
                      width: double.infinity,
                      height: 60,
                      child: ElevatedButton(
                        onPressed: () {
                          // Handle Navigation to Dashboard or Authentication
                        },
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF0F172A), // Dark elegant button
                          foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(16),
                          ),
                          elevation: 0,
                        ),
                        child: const Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Text(
                              'Get Started',
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w600,
                                letterSpacing: 0.5,
                              ),
                            ),
                            SizedBox(width: 8),
                            Icon(Icons.arrow_forward_rounded, size: 20),
                          ],
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 24),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  // Helper widget for the service badges
  Widget _buildServiceBadge(IconData icon, String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.7),
        borderRadius: BorderRadius.circular(30),
        border: Border.all(color: Colors.white, width: 1.5),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: const Color(0xFF1E3A8A)),
          const SizedBox(width: 8),
          Text(
            label,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: Color(0xFF334155),
            ),
          ),
        ],
      ),
    );
  }
}

// Custom Helper Widget for staggered Fade + Slide In Animation
class AnimatedAnimatedOpacityAndSlide extends StatelessWidget {
  final bool animate;
  final int delayMs;
  final Widget child;

  const AnimatedAnimatedOpacityAndSlide({
    Key? super.key,
    required this.animate,
    required this.delayMs,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    return AnimatedAnimatedOpacity(
      duration: Duration(milliseconds: 600 + delayMs),
      opacity: animate ? 1.0 : 0.0,
      curve: Curves.easeOutCBR,
      child: AnimatedPadding(
        duration: Duration(milliseconds: 500 + delayMs),
        padding: EdgeInsets.only(top: animate ? 0.0 : 30.0),
        curve: Curves.easeOutBack,
        child: child,
      ),
    );
  }
}

// Quick custom curve extension for a smoother premium aesthetic
class Curves {
  static const Curve easeOutCBR = Cubic(0.215, 0.610, 0.355, 1.0);
  static const Curve easeOutBack = Cubic(0.175, 0.885, 0.32, 1.1);
}