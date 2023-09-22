#include <iostream>

using namespace std;

/*
验证（）和||的执行顺序

输出：
2()
3()
2||

结论：()和||在表达式中总是先执行()
*/

class Wrapper {
public:
    Wrapper(int i): val_(i) {};

    Wrapper& operator() () {
        cout << val_ << "()" << endl;
        return *this;
    }

    // 注意改为const成员函数
    Wrapper operator||(const Wrapper& other) {
        cout << val_ << "||" << endl;
        return Wrapper(this->val_ * other.val_);
    }

    int val_{};
};

int main() {
    Wrapper w1(2);
    Wrapper w2(3);
    w1() || w2();
}